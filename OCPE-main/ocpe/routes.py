from functools import wraps
from time import sleep
from flask import render_template, url_for, flash, redirect, request
from ocpe import app, db, bcrypt
from ocpe.forms import CodeForm, ModifyProblemForm, PostProblemForm, SignupForm, LoginForm, SubmissionForm
from ocpe.models import User, Contestant, Judge, Submission, Problem
from flask_login import login_user, current_user, logout_user, login_required
from ocpe.forms import SignupForm
from sphere_engine import ProblemsClientV4
from sphere_engine.exceptions import SphereEngineException
import subprocess, os
from subprocess import PIPE

accessToken='a087837341bbe629b835cd9382f6d984'
endpoint='50e77046.problems.sphere-engine.com'

client = ProblemsClientV4(accessToken, endpoint)

#have to access problems from database
def contestant_required(func):
    '''If you decorate a view with this, it will ensure that the current user is a contestant'''
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if (not current_user.is_anonymous) and current_user.GetType() != "contestant":
            flash('Login as contestant to access this page.', 'danger')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        return func(*args, **kwargs)
    return decorated_view


def judge_required(func):
    '''If you decorate a view with this, it will ensure that the current user is a judge'''
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if (not current_user.is_anonymous) and current_user.GetType() != "judge":
            flash('Login as judge to access this page.', 'danger')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        return func(*args, **kwargs)
    return decorated_view

def compiler_output(code,inp):
    # file existance check
    if not os.path.exists('./files/test.c'):
        os.open('./files/test.c',os.O_CREAT)
    # creating a file descriptor
    fd=os.open("./files/test.c",os.O_WRONLY)
    # truncate the content of the file to 0 bytes to prevent overwriting
    os.truncate(fd,0)
    # encode the string into bytes.
    fileadd=str.encode(code)
    # write to the file.
    os.write(fd,fileadd)
    # close the file descriptor.
    os.close(fd)
    # Compiling the c program file and retrieving the error if any. 
    s=subprocess.run(['gcc','-o','./files/new','./files/test.c'],stderr=PIPE,)
    #checking whether program compiled succesfully or not.
    if s.returncode==0:
        #executing the program with input.
        r=subprocess.run(["./files/new.exe"],input=inp.encode(),stdout=PIPE)
		#return the output of the program.	
        return r.stdout.decode("utf-8")
    else:
		#return the error if the program did not compile successfully
        return s.stderr.decode("utf-8")


@app.route("/")
@app.route("/home", methods=['GET', 'POST'])
def home():
    form = CodeForm()
    if form.validate_on_submit():
        code = form.code.data
        inp = form.input.data
        form.output.data = compiler_output(code, inp)
        return render_template('index.html', form=form)
    return render_template('index.html', form=form)

@app.route("/signup", methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = SignupForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        type = form.type.data
        if type=='judge':
            user = Judge(username=form.username.data, email=form.email.data, password=hashed_password, type=type)
        else:
            user = Contestant(username=form.username.data, email=form.email.data, password=hashed_password, type=type)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html', title='Signup', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user1 = User.query.filter_by(email=form.credential.data).first()
        user2 = User.query.filter_by(username=form.credential.data).first()
        if user1:
            user=user1
        else:
            user=user2
        if (user1 or user2) and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    flash('Logout Successful!', 'success')
    next_page = request.args.get('next')
    return redirect(next_page) if next_page else redirect(url_for('home'))


# @app.route("/account")
# @login_required
# def account():
#     return render_template('account.html', title='Account')

# extra routes
@app.route("/contests")
def contests():
   return render_template('contests.html', title='Contests')

@app.route("/contest")
def contest():
   return render_template('contest.html', title='Contest #')
# end extra routes

@app.route("/create_problem", methods=['GET', 'POST'])
@login_required
@judge_required
def create_problem():
    form = PostProblemForm()
    if form.validate_on_submit():
        problem = Problem(name=form.name.data, title=form.title.data, description=form.description.data, testInput=form.testInput.data, testOutput=form.testOutput.data, score=form.score.data, timeLimit=form.timeLimit.data, judge_id = current_user.GetId())
        name = form.name.data
	
        try:
            response = client.problems.create(name,body=problem.description, masterjudge_id=1001)
            problem.id=response['id']
        except SphereEngineException as e:
            if e.code == 401:
                print('Invalid access token')
            elif e.code == 400:
                print('Error code: ' + str(e.error_code) + ', details available in the message: ' + str(e))
        try:
            response = client.problems.createTestcase(problem.id, problem.testInput, problem.testOutput,problem.timeLimit, 1)
    # check which judge id,for now set as 10,exact judge
    # response['number'] stores the number of created testcase
        except SphereEngineException as e:
            if e.code == 401:
                 print('Invalid access token')
            elif e.code == 403:
                print('Access to the problem is forbidden')
            elif e.code == 404:
                print('Problem does not exist')    
            elif e.code == 400:
                print('Error code: ' + str(e.error_code) + ', details available in the message: ' + str(e))
        db.session.add(problem)
        db.session.commit()
        flash('The problem has been added to practice section!', 'success')
        return redirect(url_for('home'))
    return render_template('create_problem.html', title='Problems', form=form)

#this is where problems will appear as in codechef front page
@app.route("/practice")
@login_required
@contestant_required
def practice():
    problems = Problem.query.all()
    return render_template('practice.html',title="Practice", problems=problems)		


# Use of <converter: variable name> in the
# route() decorator.
@app.route('/problem/<problemId>', methods=['GET'])
@login_required
@contestant_required
def problem(problemId):
    problem = Problem.query.filter_by(id=problemId).first()
    if problem:
        return render_template('question.html', title= f"Problem {problemId}", problem=problem)
    else:
        return render_template('404.html', title="404")

@app.route('/solve/<problemId>',methods=['GET','POST'])
@login_required
@contestant_required
def solve(problemId):
    form=SubmissionForm()
    problem = Problem.query.filter_by(id=problemId).first()
    if problem:
        if form.validate_on_submit():
            submission = Submission(contestant_id=current_user.GetId(), problem_id=problemId, code=form.code.data)
            source=submission.code
            compiler=11
            try:
                response = client.submissions.create(problemId, source, compiler)
                submission.id=response['id']
            except SphereEngineException as e:
                if e.code == 401:
                    print('Invalid access token')
                elif e.code == 402:
                    print('Unable to create submission')
                elif e.code == 400:
                    print('Error code: ' + str(e.error_code) + ', details available in the message: ' + str(e))

            try:
                response = client.submissions.get(submission.id)
                while response['result']['status']['code'] <=8:
                    # repeat for half time limit to avoid repeated API calls
                    sleep(min(3, problem.timeLimit / 2))
                    response = client.submissions.get(submission.id)

            except SphereEngineException as e:
                if e.code == 401:
                    print('Invalid access token')
                elif e.code == 403:
                    print('Access to the submission is forbidden')
                elif e.code == 404:
                    print('Submission does not exist')
            
            print(response['result']['status']['name'])
            print(response['result']['score'])
            print(response['result']['time'])
            print(response['result']['memory'])
            print(response['result']['signal'])
            submission.status = response['result']['status']['name']
            submission.score = response['result']['score']
            submission.time = response['result']['time']
            submission.memory = response['result']['memory']
            submission.signal = response['result']['signal']
            db.session.add(submission)
            db.session.commit()
            #display these data on a new webpage
            return redirect(url_for('result', submissionId=submission.id))

        return render_template('solve.html',title="Solve", form=form, problem=problem)#where to redirect it
        #response contains several parameters,we can use them 
    else:
        return render_template('404.html', title="404") 


@app.route('/result/<submissionId>',methods=['GET'])
@login_required
@contestant_required
def result(submissionId):
    submission = Submission.query.filter_by(id = submissionId).first()
    if submission:
        problem = Problem.query.filter_by(id=submission.problem_id).first()
        return render_template('result.html', title="Result", submission=submission, problem=problem)
    else:
        return render_template('404.html', title="404")
    
@app.route('/problems')
@login_required
@judge_required
def problems():
    problemset = Problem.query.filter_by(judge_id = current_user.GetId())
    return render_template('list_problem.html', title="Problems", problemset=problemset, judge=current_user)


@app.route('/modify_problem/<problemId>',methods=['GET','POST'])
@login_required
@judge_required
def modify_problem(problemId):
    problem = Problem.query.filter_by(id=problemId).first()
    form = ModifyProblemForm(obj = problem)
    if problem:
        if problem.judge_id == current_user.GetId():
            if form.validate_on_submit():
                problem.name = form.name.data
                problem.title = form.title.data
                problem.description = form.description.data
                problem.testInput = form.testInput.data
                problem.testOutput = form.testOutput.data
                problem.score = form.score.data
                problem.timeLimit = form.timeLimit.data
                print(problem.description)
            #Swarup, write code to modify problem in the API here
                
                # try:
                #     response = client.problems.create(name,body=problem.description, masterjudge_id=1001)
                #     problem.id=response['id']
                # except SphereEngineException as e:
                #     if e.code == 401:
                #         print('Invalid access token')
                #     elif e.code == 400:
                #         print('Error code: ' + str(e.error_code) + ', details available in the message: ' + str(e))
                # try:
                #     response = client.problems.createTestcase(problem.id, problem.testInput, problem.testOutput,problem.timeLimit, 1)
            # check which judge id,for now set as 10,exact judge
            # response['number'] stores the number of created testcase
                # except SphereEngineException as e:
                #     if e.code == 401:
                #         print('Invalid access token')
                #     elif e.code == 403:
                #         print('Access to the problem is forbidden')
                #     elif e.code == 404:
                #         print('Problem does not exist')    
                #     elif e.code == 400:
                #         print('Error code: ' + str(e.error_code) + ', details available in the message: ' + str(e))
                # db.session.add(problem)
                # db.session.commit()
                try:
                   client.problems.update(problem.id,name=problem.name,body=problem.description)
                except SphereEngineException as e:
                    if e.code == 401:
                        print('Invalid access token')
                    elif e.code == 403:
                        print('Access to the problem is forbidden')
                    elif e.code == 404:
                        print('Problem does not exist')
                    elif e.code == 400:
                        print('Error code: ' + str(e.error_code) + ', details available in the message: ' + str(e))
        
#score data useless cannot change score        
    
                try:
                    client.problems.updateTestcase(problem.id,0,problem.testInput,problem.testOutput,problem.timeLimit)
                except SphereEngineException as e:
                    if e.code == 401:
                        print('Invalid access token')
                    elif e.code == 403:
                        print('Access to the problem is forbidden')
                    elif e.code == 404:
                        print('Non existing resource, error code: ' + str(e.error_code) + ', details available in the message: ' + str(e))
                    elif e.code == 400:
                        print('Error code: ' + str(e.error_code) + ', details available in the message: ' + str(e))   
                
                flash('The modified and added to practice section!', 'success')
                db.commit()
                return redirect(url_for('home'))

                

            return render_template('modify_problem.html',title="Modify", form=form, problem=problem)#where to redirect it
            #response contains several parameters,we can use them 
        else:
            flash('You must be the author of this problem to modify it!', 'danger')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
    else:
        return render_template('404.html', title="404") 
       
@app.route('/guide')
def guide():
    return render_template('guide.html', title="Guide")
    
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html', title="404")
