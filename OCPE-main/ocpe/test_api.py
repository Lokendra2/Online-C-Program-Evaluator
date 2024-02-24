"""
Example presents error handling for submissions.create() API method
"""
from sphere_engine import ProblemsClientV3
from sphere_engine.exceptions import SphereEngineException

# define access parameters
accessToken = 'a087837341bbe629b835cd9382f6d984'
endpoint = '50e77046.problems.sphere-engine.com'

# initialization
client = ProblemsClientV3(accessToken, endpoint)

# API usage
problemCode = 'TEST'
source = '#include<stdio.h> int main(){printf("%d",a);} '
nonexistingCompiler = 11
response={}
print('hello')
try:
    print('hello')
    response = client.submissions.create(problemCode, source, nonexistingCompiler)
    # response['id'] stores the ID of the created submission
    print('hello')
    print(response['id'])
    print(type(response))
except SphereEngineException as e: 
    print(response)
    if e.code == 401:
        print('Invalid access token')
    elif e.code == 404:
        # aggregates three possible reasons of 404 error
        # non existing problem, compiler or user
        print('Non existing resource (problem, compiler or user), details available in the message: ' + str(e))
    elif e.code == 400:
        print('Empty source code')
