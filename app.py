import os
import json
import urllib
import boto3
import botocore
from flask import Flask
from flask_restful import Resource, Api, reqparse
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.utils import secure_filename

S3_BUCKET                 = os.environ['S3_BUCKET_NAME']
S3_KEY                    = os.environ['S3_ACCESS_KEY']
S3_SECRET                 = os.environ['S3_SECRET_ACCESS_KEY']
GITHUB_TOKEN              = os.environ['GIT_TOKEN']
S3_LOCATION               = 'http://{}.s3.amazonaws.com/'.format(S3_BUCKET)

storage = {}
storage['gitData'] = {}
storage['discourse'] = {'frontpage': {}, 'topics': {}}

git_urls = ['repos/Edgeryders-Participio/realities/stats/code_frequency', 'repos/Edgeryders-Participio/realities/contributors']
discourse_root_url = 'https://edgeryders.eu'
discourse_categories = ['/c/participio', '/c/blivande', '/c/blivande/blivande-web-content']
discourse_front_page_content = ['9176','9179','9180','9181','9182','9184','9199','9290', '9391', '9392', '9393', '9394', '9398', '9397', '9400', '9401', '9402', '9403']

s3 = boto3.client(
   "s3",
   aws_access_key_id=S3_KEY,
   aws_secret_access_key=S3_SECRET
)

def upload_file_to_s3(file, bucket_name, key, acl="public-read" ):
    try:
        with open(file, 'rb') as data:
            s3.upload_fileobj(
                data,
                bucket_name,
                file,
                ExtraArgs={
                    "ACL": acl,
                    'ServerSideEncryption': "AES256"            
                }
        )

    except Exception as e:
        print("Something Happened: ", e)
        return e

    return "{}{}".format(S3_LOCATION, file)

def fetch_data_from_git_api():
    print('Getting Git data')
    root_url = 'https://api.github.com/'
    for gitpath in git_urls:
        path = root_url + gitpath  
        rq = urllib.request.Request(path)
        rq.add_header('Authorization', 'token %s' % GITHUB_TOKEN)
        with urllib.request.urlopen(rq) as url:
            data = json.loads(url.read().decode())
            storage['gitData'][gitpath] = data

def fetch_topics_from_discourse_api():
    print('Getting Discourse data')
    s3data = s3.list_objects_v2(Bucket=S3_BUCKET)['Contents']
    s3avatars = [o['Key'][17:] for o in s3data if 'instance/avatars/' in o['Key']]
    for category in discourse_categories:
        tempData = {'users': {}, 'topic_list': {'topics': {}}}
        page = 0
        more = True
        while more:
            path = discourse_root_url + category + '.json?page=' + str(page)
            rq = urllib.request.Request(path)
            with urllib.request.urlopen(rq) as url:
                pageData = json.loads(url.read().decode())
                for user in pageData['users']:
                    if user['id'] not in tempData['users']:
                        newUser = {'id': user['id'], 'username': user['username'], 'presentation': {}, 'name': '', 'public': False}
                        if user['avatar_template'][:4] != 'http':
                            newUser['avatar_template'] = discourse_root_url + user['avatar_template'].replace("{size}","50")
                            newUser['large_avatar'] = discourse_root_url + user['avatar_template'].replace("{size}","500")
                        else:
                            newUser['avatar_template'] = user['avatar_template'].replace("{size}","50")
                            newUser['large_avatar'] = user['avatar_template'].replace("{size}","500")
                        try:
                            urllib.request.urlretrieve(newUser['avatar_template'], 'instance/avatars/' + user['username'] + '.png')
                            output = upload_file_to_s3('instance/avatars/' + user['username'] + '.png', S3_BUCKET, user['username'] + '.png')
                            newUser['avatar_template'] = output
                        except:
                          newUser['avatar_template'] = 'https://via.placeholder.com/50.png'
                          print("Could not find " + 'instance/avatars/' + user['username'] + '.png')
                        tempData['users'][user['id']] = newUser
                for topic in pageData['topic_list']['topics']:
                    if not topic['id'] in tempData['topic_list']['topics']:
                        tempData['topic_list']['topics'][topic['id']] = topic
                        post_url = discourse_root_url + '/posts/' + str(topic['topic_post_id']) + '.json'
                        rq = urllib.request.Request(post_url)
                        with urllib.request.urlopen(rq) as url:
                            postData = json.loads(url.read().decode())
                            tempData['topic_list']['topics'][topic['id']]['post'] = postData['raw']
                        if 'blivande-presentation' in topic['tags']:
                            tempData['users'][topic['posters'][0]['user_id']]['presentation'] = tempData['topic_list']['topics'][topic['id']]['post']
                            tempData['users'][topic['posters'][0]['user_id']]['name'] = tempData['topic_list']['topics'][topic['id']]['title']
                            tempData['users'][topic['posters'][0]['user_id']]['public'] = True
                if 'more_topics_url' in pageData['topic_list']:
                    page += 1
                else:
                    more = False
        storage['discourse'][category] = tempData

def fetch_frontpage_content_from_discourse_api():
    print('Getting frontpage content from Discourse data')
    for topic in discourse_front_page_content:
        path = discourse_root_url + '/raw/' + topic + '.json'
        rq = urllib.request.Request(path)
        with urllib.request.urlopen(rq) as url:
            pageData = url.read().decode()
            storage['discourse']['frontpage'][topic] = pageData

app = Flask(__name__)
api = Api(app)
sched = BackgroundScheduler()
sched.start()
sched.add_job(fetch_data_from_git_api, 'interval', minutes=10)
sched.add_job(fetch_topics_from_discourse_api, 'interval', minutes=10)
sched.add_job(fetch_frontpage_content_from_discourse_api, 'interval', minutes=10)
fetch_topics_from_discourse_api()
fetch_frontpage_content_from_discourse_api()
fetch_data_from_git_api()

class getGitData(Resource):
    def get(self):
        return storage['gitData']

class getParticipioTopics(Resource):
    def get(self):
        return storage['discourse']['/c/participio']

class getBlivandeTopics(Resource):
    def get(self):
        return storage['discourse']['/c/blivande/blivande-web-content']

class getBlivandePresentations(Resource):
    def get(self):
        users = storage['discourse']['/c/blivande/blivande-web-content']['users']
        presentations = {key:value for (key,value) in users.items() if value['public'] == 1}
        return presentations

class getBlivandeFrontpageContent(Resource):
    def get(self):
        return storage['discourse']['frontpage']

api.add_resource(getGitData, '/')
api.add_resource(getParticipioTopics, '/discourse/participio')
api.add_resource(getBlivandeTopics, '/discourse/blivande')
api.add_resource(getBlivandePresentations, '/discourse/blivande/presentations')
api.add_resource(getBlivandeFrontpageContent, '/discourse/blivande/frontpage')


if __name__ == '__main__':
    os.makedirs(os.path.join(app.instance_path, 'avatars'), exist_ok=True)
    app.run(debug=True, threaded=True)