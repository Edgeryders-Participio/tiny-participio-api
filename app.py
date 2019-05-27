import os
import json
import urllib
from flask import Flask
from flask_restful import Resource, Api, reqparse
from apscheduler.schedulers.background import BackgroundScheduler

storage = {}
storage['discourse'] = {'frontpage': {}, 'topics': {}}

discourse_root_url = 'https://forum.blivande.com/'
discourse_categories = ['/c/congregation', '/c/tau', '/c/beta', '/c/events', '/c/web']
discourse_front_page_content = ['77','66','67','78','68','36','50','51','52','53','54','56','55','57','58','59','60']


def fetch_topics_from_discourse_api():
    print('Getting Discourse data')
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
                        tempData['users'][user['id']] = newUser
                for topic in pageData['topic_list']['topics']:
                    if not topic['id'] in tempData['topic_list']['topics']:
                        tempData['topic_list']['topics'][topic['id']] = topic
                        topicUrl = discourse_root_url + 't/' + str(topic['id']) + '.json'
                        rq = urllib.request.Request(topicUrl)
                        with urllib.request.urlopen(rq) as url:
                            topicData = json.loads(url.read().decode())
                            postUrl = discourse_root_url + 'posts/' + str(topicData['post_stream']['posts'][0]['id']) + '.json'
                            print('Getting ' + postUrl)
                            rq = urllib.request.Request(postUrl)
                            with urllib.request.urlopen(rq) as url:
                                postData = json.loads(url.read().decode())
                                tempData['topic_list']['topics'][topic['id']]['post'] = postData['raw']
                        if 'web-presentation' in topic['tags']:
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
#sched = BackgroundScheduler()
#sched.start()
#sched.add_job(fetch_topics_from_discourse_api, 'interval', minutes=10)
#sched.add_job(fetch_frontpage_content_from_discourse_api, 'interval', minutes=10)

class getBlivandeTopics(Resource):
    def get(self):
        return storage['discourse']['/c/web']

class getBlivandePresentations(Resource):
    def get(self):
        users = storage['discourse']['/c/web']['users']
        presentations = {key:value for (key,value) in users.items() if value['public'] == 1}
        return presentations

class getBlivandeFrontpageContent(Resource):
    def get(self):
        return storage['discourse']['frontpage']

api.add_resource(getBlivandeTopics, '/discourse/blivande')
api.add_resource(getBlivandePresentations, '/discourse/blivande/presentations')
api.add_resource(getBlivandeFrontpageContent, '/discourse/blivande/frontpage')


if __name__ == '__main__':
    fetch_topics_from_discourse_api()
    fetch_frontpage_content_from_discourse_api()
    os.makedirs(os.path.join(app.instance_path, 'avatars'), exist_ok=True)
    app.run(debug=True, threaded=True)