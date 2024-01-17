def create_github_repo(org_name, token, repo_name, repo_description, is_private):
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    
    data = '{"name":"' + repo_name + '","description":"' + repo_description + '","homepage":"https://github.com","private":'+ 'true' if is_private else 'false' + ',"has_issues":true,"has_projects":true,"has_wiki":true}'

    response = requests.post('https://api.github.com/orgs/' + org_name + '/repos', headers=headers, data=data)
    
    return response
 