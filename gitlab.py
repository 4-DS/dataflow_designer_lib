import requests
import re

from html.parser import HTMLParser
 
class Parse(HTMLParser):
    def __init__(self):
    #Since Python 3, we need to call the __init__() function of the parent class
        super().__init__()
        self.reset()
    #Defining what the method should output when called by HTMLParser.
    def handle_starttag(self, tag, attrs):
        # Only parse the 'anchor' tag.
        #self.data = ''
        if tag == "meta":
           #self.data += tag
           #print(tag)
           for name,csrf_token in attrs:
               
               if csrf_token == "csrf-token":
                   content,token = attrs[1]
                
                   self.data = token
                   break


def get_gitlab_session(git_provider_url, gitlab_username, gitlab_password):

    
    GIT_PROVIDER_SIGN_IN_URL = f'{git_provider_url}users/sign_in'
    GIT_PROVIDER_LOGIN_URL = f'{git_provider_url}users/sign_in'
    
    session = requests.Session()
    
    sign_in_page = str(session.get(GIT_PROVIDER_SIGN_IN_URL).content)
    for l in sign_in_page.split('\n'):
        m = re.search('name="authenticity_token" value="([^"]+)"', l)
        if m:
            break
    
    token = None
    if m:
        token = m.group(1)
    
    if not token:
        print('Unable to find the authenticity token')
        sys.exit(1)
    
    data = {'user[login]': gitlab_username,
            'user[password]': gitlab_password,
            'authenticity_token': token}
    r = session.post(GIT_PROVIDER_LOGIN_URL, data=data)
    if r.status_code != 200:
        print(f'Failed to log in to GitLab {GIT_PROVIDER_LOGIN_URL}')
        sys.exit(1)

    page_tokens = session.get('/'.join((git_provider_url, '-/user_settings/personal_access_tokens')))
    private_token = None
    if page_tokens.ok:
        p = Parse()
        p.feed(page_tokens.text)
        token = p.data
        
        body = {
            "personal_access_token[name]": 'mytoken',
            "personal_access_token[scopes][]": 'api',
            'authenticity_token': token
        }
        
    response = session.post('/'.join((git_provider_url, '-/user_settings/personal_access_tokens')), data=body)
        
    if response.ok:
        private_token = response.json()['new_token']
        
    if not private_token:
        sys.exit(1)
    session.headers.update({'Private-Token': private_token})
    return session

def get_gitlab_group_id(git_provider_api, gitlab_session, group_name, parent_group_id=None):
    r = gitlab_session.get(f'{git_provider_api}/groups')
    for group in r.json():
        if group["name"] == group_name and (group["parent_id"] == parent_group_id if parent_group_id else not group["parent_id"]):
            return group["id"]
    return None

def create_gitlab_group(git_provider_api, gitlab_session, group_name, parent_group_id):

    group_id = get_gitlab_group_id(git_provider_api, gitlab_session, group_name, parent_group_id)
    
    if not group_id:
        headers = {
    #        'PRIVATE-TOKEN': token,
            'Content-Type': 'application/json',
        }
        
        data = '{"path": "'+ group_name + '", "name": "'+ group_name +'", "parent_id": '+ str(parent_group_id) +' }'
    
        response = gitlab_session.post(f'{git_provider_api}/groups/', headers=headers, data=data)
        
        group_id = response.json()["id"]
    
    return group_id

def create_gitlab_repo(*, git_provider_api, gitlab_session, repo_group_id, repo_name, repo_description, is_private):

    if check_gitlab_project_exists(git_provider_api, gitlab_session, repo_group_id, repo_name):
        headers = {
    #        'PRIVATE-TOKEN': token,
            'Content-Type': 'application/json',
        }
        
        data = '{"path": "'+ repo_name + '", "name": "'+ repo_name +'", "namespace_id": '+ str(repo_group_id) +', "description": "' + repo_description + '", "visibility": ' + "private" if is_private else "public" + '}'
    
        data = '{"name": "'+ repo_name +'", "namespace_id": '+ str(repo_group_id) + ' }'
        response = gitlab_session.post(f'{git_provider_api}/projects/', headers=headers, data=data)
        
        return response

def get_pipeline_steps(*, git_provider_api, gitlab_session, group_id):
    
    response = gitlab_session.get(f'{git_provider_api}/groups/{group_id}/projects')
    
    response.raise_for_status()

    projects_list = response.json()
    step_list = [{"step_repo_name": project["name"], "step_repo_git": project["http_url_to_repo"]} for project in projects_list]

    return step_list
    
def check_gitlab_project_exists(git_provider_api, gitlab_session, group_id, project_name):
    
    response = gitlab_session.get(f'{git_provider_api}/groups/{group_id}/projects')
    
    response.raise_for_status()

    projects_list = response.json()
    for project in projects_list:
        if project["name"] == project_name:
            return True
        
    return False