import json
import os
import re
import requests
import sys
import yaml
import importlib
import pprint

from pathlib import Path
from subprocess import STDOUT, run, call
from getpass import getpass
from urllib.parse import urlparse, urlunparse

from .step_utils import create_step, get_step_folders
from dataflow_designer_lib.github import create_github_repo

from dataflow_designer_lib.common import get_tmp_prepared 

pp = pprint.PrettyPrinter(indent=4)

def set_git_creds_for_subprocess(git_username, git_password):
    child_env = os.environ.copy()
    child_env["GIT_USER"] = git_username
    child_env["GIT_PASSWORD"] = git_password
    return child_env

class SinaraPipelineProvider():

    # def __init__(self):

    #     self.git_provider = input("Please, enter your Git provider among GitHub/GitLab (default=GitLab): ") or 'GitLab'
        
    #     if self.git_provider == 'GitLab':
    #         self.provider = importlib.import_module('dataflow_designer_lib.gitlab')
    #     elif self.git_provider == 'GitHub':
    #         self.provider = importlib.import_module('dataflow_designer_lib.github')

    def get_git_provider(self, git_provider_type):
        if git_provider_type == 'GitLab':
            git_provider = importlib.import_module('dataflow_designer_lib.gitlab')
        elif git_provider_type == 'GitHub':
            git_provider = importlib.import_module('dataflow_designer_lib.github')
        return git_provider

    def cache_git_creds(self, git_provider_url, git_username, git_password):
        if git_username and git_password:
            print(git_provider_url)
            # print(git_username)
            # print(git_password)
            # exit(0)
            print("WARNING: Git credentials are stored only plain text. It's a normal behaviour.")
            run_result = run(f"git config --global credential.helper store && \
                                   (echo url={git_provider_url}; echo username={git_username}; echo password='{git_password}'; echo ) | git credential approve",
                                     shell=True, stderr=STDOUT, cwd=None)
            if run_result.returncode !=0:
                raise Exception(f'Could not store Git credentials!')


    def create_pipeline(self, pipeline_manifest_path, pipeline_dir, pipeline_name,
                        git_provider, git_default_branch = 'main',
                        git_step_template_url = None, step_template_nb_substep = None, git_step_template_username = None, git_step_template_password = None,
                        git_username = None, git_useremail = None):

        # _pipeline_manifest_path = str(Path(__file__).parent.parent.resolve()) + '/' + pipeline_manifest_path

        # print(f'Trying pipeline manifest in {_pipeline_manifest_path}')

        # arg_parser = ArgumentParser()
        
        # #arg_parser.add_argument("--git_provider_step_template_url", help="git provider base url where step template resides")    
        # arg_parser.add_argument("--git_provider_organization_api", help="git provider api url in organization ")    
        # arg_parser.add_argument("--git_provider_organization_url", help="git provider base url in organization")

        # arg_parser.add_argument("--git_step_template_url", help="step template url")
        # arg_parser.add_argument("--step_template_nb_substep", help="the main notebook in step template")
        # arg_parser.add_argument("--current_dir", help="current directory")      
        # arg_parser.add_argument("--git_step_template_username", help="login to clone step template")
        # arg_parser.add_argument("--git_step_template_password", help="password to clone step template")
        
        # args = arg_parser.parse_args()
        
        # SNR_STEP_TEMPLATE = args.git_step_template_url
        # SNR_STEP_TEMPLATE_SUBSTEP = args.step_template_nb_substep
        # CURRENT_DIR = args.current_dir
        
        # git_public_user_sent = args.git_step_template_username is not None and args.git_step_template_password
        # if git_public_user_sent:
        #     GIT_STEP_TEMPLATE_USERNAME = args.git_step_template_username
        #     GIT_STEP_TEMPLATE_PASSWORD = args.git_step_template_password

        # git_provider = self.git_provider #input("Please, enter your Git provider among GitHub/GitLab (default=GitLab): ") or 'GitLab'
        # product_name = None
        # if git_provider == 'GitLab':
        #     product_name = input("Please, enter your Product name: ") or 'fabric_test_product'
        # elif git_provider == 'GitHub':
        #     pass
        
        # pipeline_name = input("Please, enter your Pipeline name: ") or 'fabric_test_pipeline'
        # pipeline_folder = input(f"Please, enter a folder to save '{pipeline_name}': ") or str(Path(CURRENT_DIR).resolve())
        
        # git_default_branch = input("Please, enter your Git default branch: ")
        # git_username = input("Please, enter your Git user name (default=data_scientist_name): ") or "data_scientist_name"
        # git_useremail = input("Please, enter your Git user email (default=data_scientist_name@example.com): ") or "data_scientist_name@example.com"

        git_provider_url = urlparse(git_step_template_url)
        git_provider_url = f'{git_provider_url.scheme}://{git_provider_url.netloc}'
        #print(git_provider_url)
        #exit(0)
        self.cache_git_creds(git_step_template_url, git_username, git_step_template_password)
        
        with open(pipeline_manifest_path) as f:
            p_manifest_dict = yaml.safe_load(f)

        pipeline_dir = pipeline_dir + '/'+ pipeline_name
        os.makedirs(pipeline_dir, exist_ok=True)
            
        for step in p_manifest_dict["steps"]:
            step_name = step["step_name"]
 
            step_repo_name = ''
            if git_provider == 'GitLab':
                step_repo_name = f"{step_name}"
            elif git_provider == 'GitHub':
                step_repo_name = f"{pipeline_name}-{step_name}"
                
            step_repo_path = pipeline_dir + "/" + step_repo_name + "/"

            run_result = None
            if not git_step_template_username is None:
                child_env = set_git_creds_for_subprocess(git_step_template_username, git_step_template_password)
                run_result = run(f"rm -rf {step_repo_name} && \
                                   git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' clone --recursive {git_step_template_url} {step_repo_name} && \
                                   cd {step_repo_name} && \
                                   export current_branch=$(git rev-parse --abbrev-ref HEAD) && \
                                   [[ $(git rev-parse --verify {git_default_branch} 2>/dev/null) ]] && echo 'Branch {git_default_branch} is already exists' || (git checkout -b {git_default_branch}; git branch -d $current_branch;) && \
                                   git config user.email {git_useremail} && \
                                   git config user.name {git_username}",
                                   universal_newlines=True,
                                   shell=True,
                                   env=child_env,
                                   stderr=STDOUT, 
                                   cwd=pipeline_dir, 
                                   executable="/bin/bash")
                                     
            else:
                run_result = run(f'rm -rf {step_repo_name} && \
                               git clone --recurse-submodules {git_step_template_url} {step_repo_name} && \
                               cd {step_repo_name} && \
                               export current_branch=$(git rev-parse --abbrev-ref HEAD) && \
                               [[ $(git rev-parse --verify {git_default_branch} 2>/dev/null) ]] && echo "Branch {git_default_branch} is already exists" || (git checkout -b {git_default_branch}; git branch -d $current_branch;) && \
                               git config user.email {git_useremail} && \
                               git config user.name {git_username}', 
                             shell=True, stderr=STDOUT, cwd=pipeline_dir, executable="/bin/bash")
        
            if run_result.returncode !=0:
                raise Exception(f'Could not prepare a repository for SinaraML step with the name {step_repo_name}!')

            print(f'pipeline_name {pipeline_name} step_repo_path: {step_repo_path} step["substeps"]: {step["substeps"]} step_template_nb_substep: {step_template_nb_substep}')
            create_step(pipeline_name, step_repo_path, step["substeps"], step_template_nb_substep)

            # run_result = run (f'git add -A && \
            #                     git commit -m "Adjust substep interface and step parameters" && \
            #                     git reset $(git commit-tree HEAD^{{tree}} -m "a new SinaraML step")',
            #                     shell=True, stderr=STDOUT, cwd=step_repo_path, executable="/bin/bash")
            # if run_result.returncode !=0:
            #     raise Exception(f'Could not prepare a repository for SinaraML step with the name {step_repo_name}!')

    def push_pipeline(self, pipeline_dir, pipeline_git_url,
                      git_provider_type, git_provider_url, git_provider_api,
                      git_default_branch = 'main',
                      git_username = None, git_password = None):
        # arg_parser = ArgumentParser()
        
        # #arg_parser.add_argument("--git_provider_step_template_url", help="git provider base url where step template resides")
        # arg_parser.add_argument("--git_provider_organization_api", help="git provider api url in organization ")
        # arg_parser.add_argument("--git_provider_organization_url", help="git provider base url in organization")

        # #arg_parser.add_argument("--git_step_template_url", help="step template url")
        # #arg_parser.add_argument("--step_template_nb_substep", help="the main notebook in step template")
        # arg_parser.add_argument("--current_dir", help="current directory")
        # #arg_parser.add_argument("--git_step_template_username", help="login to clone step template")
        # #arg_parser.add_argument("--git_step_template_password", help="password to clone step template")
        
        # args = arg_parser.parse_args()
        
        # CURRENT_DIR = args.current_dir
        # GIT_PROVIDER_URL = args.git_provider_organization_url
        # GIT_PROVIDER_API = args.git_provider_organization_api

        # git_provider = self.git_provider
        # #git_provider = input("Please, enter your Git provider among GitHub/GitLab (default=GitLab): ") or 'GitLab'

        # product_name = ''
        # if git_provider == 'GitLab':
        #     git_provider_organization_username = input(f"Please, enter your username for managing {git_provider} repositories: ")
        #     git_provider_organization_password = getpass(f"Please, enter your password for managing {git_provider} repositories: ")
        
        #     # products_root_name = input("Please, enter your Root group for products in your organization (default=dsml_components): ") or 'dsml_components'
        #     # product_name = input("Please, enter your Product name: ") or 'fabric_test_product'
        #     pipeline_group_path = input("Please enter pipeline full path: ")
        #     products_root_name = pipeline_group_path.split('/')[0]
        #     pipeline_name = pipeline_group_path.split('/')[-1]
            
        # elif git_provider == 'GitHub':
        #     git_provider_organization_username = input(f"Please, enter your {git_provider} organization: ")
        #     git_provider_organization_password = getpass(f"Please, enter your token for managing {git_provider} repositories: ")

        
        # #pipeline_name = input("Please, enter your Pipeline name: ") or 'fabric_test_pipeline'

        # steps_folder_glob = None
        # if git_provider == 'GitLab':
        #     steps_folder_glob = input(f"Please, enter a glob to load '{pipeline_name}' like /some_path/steps_folder/*. (default=./product_name/pipeline_name/*): ") or f"{Path(CURRENT_DIR).resolve()}/{pipeline_name}/*"
        # elif git_provider == 'GitHub':
        #     steps_folder_glob = input(f"Please, enter a glob to load '{pipeline_name}' like /some_path/steps_folder/*. (default=./pipeline_name-*): ") or f"{Path(CURRENT_DIR).resolve()}/{pipeline_name}-*"

        # git_default_branch = input("Please, enter your Git default branch: ")

#        save_git_creds = input(f"Would you like to store Git credentials once? WARNING: Currenly, only plain text is supported. y/n (default=y): ") or "y"
        
#        if save_git_creds == "y":
#            run_result = run(f"git config --global credential.helper store && \
#                               (echo url={GIT_PROVIDER_URL}; echo username={git_provider_organization_username}; echo password={git_provider_organization_password}; echo ) | git credential approve",
#                                 shell=True, stderr=STDOUT, cwd=None)
        
#            if run_result.returncode !=0 :
#                raise Exception(f'Could not store Git credentials!')
        
        self.cache_git_creds(git_provider_url, git_username, git_password)

        steps_folder_glob = f"{pipeline_dir}/*"
        step_folders = get_step_folders(steps_folder_glob)

        git_provider = self.get_git_provider(git_provider_type)
        gitlab_session = None
        if git_provider_type == 'GitLab':
            gitlab_session = git_provider.get_gitlab_session(git_provider_url, git_username, git_password)
            #products_root_name_id = git_provider.get_gitlab_group_id(git_provider_api, gitlab_session, products_root_name)
            #print(products_root_name_id)
            #product_name_id = self.provider.create_gitlab_group(GIT_PROVIDER_API, gitlab_session, product_name, products_root_name_id)
            #print(product_name_id)
            #pipeline_name_id = self.provider.create_gitlab_group(GIT_PROVIDER_API, gitlab_session, pipeline_name, product_name_id)
            pipeline_group_path = urlparse(pipeline_git_url).path[1::] # remove root slash
            pipeline_name_id = git_provider.get_gitlab_group_id2(git_provider_api, gitlab_session, pipeline_group_path)
            print(pipeline_name_id)

        print(f'You are about co push following steps to to the {git_provider_url} repo:')
        for step_folder in step_folders:
            print(step_folder)
        yes = input("Continue? (Y/n):")
        if yes and not yes.lower().startswith('y'):
            return

        for step_folder in step_folders:
            step_name = None
            step_repo_git = None
            if git_provider_type == 'GitLab':
                step_name = Path(step_folder).name
                pipeline_name = pipeline_git_url.split('/')[-1]
            elif git_provider_type == 'GitHub':
                step_folder_split = Path(step_folder).name.split("-")
                step_name = '-'.join(step_folder_split[1::]) if len(step_folder_split) > 1 else None
                pipeline_name = step_folder_split[0]
    
            if step_name:
                if git_provider_type == 'GitLab':
                    step_repo_name = f"{step_name}"
                    #step_repo_git = f"{GIT_PROVIDER_URL}/{products_root_name}/{product_name}/{pipeline_name}/{step_repo_name}.git"
                    step_repo_git = f"{pipeline_git_url}/{step_repo_name}.git"
                    # create GitLab repo for a step

                    response = git_provider.create_gitlab_repo(git_provider_api=git_provider_api,
                                                                gitlab_session=gitlab_session,
                                                                repo_group_id=pipeline_name_id,
                                                                repo_name=step_repo_name,
                                                                repo_description='This is your ' + step_name + ' step in pipeline ' + pipeline_name,
                                                                is_private=True)
              
                elif git_provider_type == 'GitHub':
                    step_repo_name = f"{pipeline_name}-{step_name}"
                    #step_repo_name = step_name
                    step_repo_git = f"{pipeline_git_url}/{step_repo_name}.git"
                    
                    git_org_name = urlparse(pipeline_git_url).path.split('/')[1]
                    
                    # create GitHub repo for a step
                    response = git_provider.create_github_repo(git_provider_api=git_provider_api,
                                                                git_provider_url=git_provider_url,
                                                                org_name=git_org_name,
                                                                token=git_password,
                                                                repo_name=step_repo_name,
                                                                repo_description='This is your ' + step_name + ' step in pipeline ' + pipeline_name,
                                                                is_private=True)
                    #print(git_provider_api)
                    #print(git_provider_url)
                    #print(git_org_name)
                    #print(response)
                child_env = set_git_creds_for_subprocess(git_username, git_password)
                run_result = run(f"git checkout {git_default_branch} && \
                                   git remote set-url origin {step_repo_git} && \
                                   git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' push --set-upstream origin {git_default_branch}",
                                   universal_newlines=True,
                                   shell=True,
                                   env=child_env,
                                   stderr=STDOUT, 
                                   cwd=step_folder,
                                   executable="/bin/bash")
                
                #run_result = run (f'git remote set-url origin {step_repo_git} && \
                #                    git push -f',
                #                   shell=True, stderr=STDOUT, cwd=step_folder, executable="/bin/bash")
                if run_result.returncode !=0 :
                    raise Exception(f'Could not push a repository for SinaraML step with the name {step_repo_name}!')

    def pull_pipeline(self, pipeline_dir, pipeline_git_url,
                      git_provider_type, git_provider_url, git_provider_api,
                      git_default_branch = 'main',
                      git_username = None, git_password = None):

        do_clone = True
        if pipeline_git_url is None or pipeline_git_url == 'None': # get pipeline git url from first pipeline step
            do_clone = False
            for step_repo_name in get_step_folders(f'{pipeline_dir}/*'):
                import subprocess
                result = subprocess.run(f'cd {step_repo_name} && git config --get remote.origin.url', shell=True, stdout=subprocess.PIPE)
                step_git_url = result.stdout.decode('utf-8').replace('\n', '')
                break
            if pipeline_git_url is None:
                raise Exception(f'Could not pull SinaraML pipeline: git repository not found!')

            parsed = urlparse(step_git_url)
            lst = parsed.path.split('/')
            git_folder = '/'.join(lst[:len(lst)-1]) # remove step name from path
            if git_provider_type == 'GitLab':
                pass
            elif git_provider_type == 'GitHub':
                git_folder = git_folder + '/' + lst[-1].split['-'][0] # add pipeline name
            url_parts = [parsed.scheme, parsed.netloc, git_folder, '', '', '']
            pipeline_git_url = urlunparse(url_parts)
        
        #print(pipeline_git_url)
        #exit(0)
        
        git_provider = self.get_git_provider(git_provider_type)
        pipeline_name = ''
        
        gitlab_session = None
        step_list = []
        if git_provider_type == 'GitLab':
            gitlab_session = git_provider.get_gitlab_session(git_provider_url, git_username, git_password)
            pipeline_group_path = urlparse(pipeline_git_url).path[1::]
            step_list = git_provider.get_gitlab_group_projects(git_provider_api, gitlab_session, pipeline_group_path)
            pipeline_name = urlparse(pipeline_git_url).path.split('/')[-1]

        elif git_provider_type == 'GitHub':

            git_org_name = urlparse(pipeline_git_url).path.split('/')[1]
            print(git_org_name)
            pipeline_name = urlparse(pipeline_git_url).path.split('/')[-1].split['-'][0]
            print(pipeline_name)
            step_list = git_provider.get_pipeline_steps(git_provider_api=git_provider_api, git_provider_url=git_provider_url,
                                                         org_name=git_org_name,
                                                         token=git_password, pipeline_name=pipeline_name)

        if do_clone:
            pipeline_dir = str(Path(pipeline_dir) / pipeline_name)
            import errno
            try:
                os.makedirs(pipeline_dir)
            except OSError as e:
                if e.errno == errno.EEXIST:
                    raise Exception(f'Could not pull SinaraML pipeline {pipeline_name}: folder already exists!')
                else:
                    raise  # raises the error again
        
        #print(pipeline_name)
        #print(step_list)
        for step in step_list:
            step_repo_name = step["step_repo_name"]
            step_repo_git = step["step_repo_git"]
            if do_clone:
                # clone
                git_command = f"clone {step_repo_git}"
                cwd = pipeline_dir
            else: 
                #pull
                git_command = f"pull"
                step_dir = Path(pipeline_dir) / step_repo_name
                cwd = step_dir

            child_env = set_git_creds_for_subprocess(git_username, git_password)
            run_result = run(f"git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' {git_command}",
                           universal_newlines=True,
                           shell=True,
                           env=child_env,
                           stderr=STDOUT, 
                           cwd=cwd,
                           executable="/bin/bash")
            
        #     tsrc_manifest_repo = {
        #         #"dest": step_repo_name,
        #         "src": step_repo_name,
        #         "url": step_repo_git,
        #         "branch": git_default_branch
        #     }
        #     tsrc_manifest["repos"].append(tsrc_manifest_repo)
            
        # with open('manifest.yml', 'w') as f:
        #     yaml.dump(tsrc_manifest, f, default_flow_style=False)
        
        # get_tmp_prepared()
        
        # tsrc_manifest_repo_path = str(Path(f"tmp/{pipeline_name}-manifest").resolve())
        # pipeline_folder_abs_path = str(Path(f"{pipeline_folder}").resolve())
        # run_result = run(f'rm -rf {pipeline_folder_abs_path}/.tsrc && \
        #            rm -rf {tsrc_manifest_repo_path}.git && \
        #            rm -rf {tsrc_manifest_repo_path} && \
        #            git init --bare {tsrc_manifest_repo_path}.git && \
        #            git clone {tsrc_manifest_repo_path}.git {tsrc_manifest_repo_path} && \
        #            cp manifest.yml {tsrc_manifest_repo_path} && \
        #            cd {tsrc_manifest_repo_path} && \
        #            git config user.email jovyan@test.ru && \
        #            git config user.name jovyan && \
        #            git add -A &&  \
        #            git commit -m "Updated tsrc manifest" && \
        #            git push && \
        #            cd {pipeline_folder_abs_path} && \
        #            tsrc init {tsrc_manifest_repo_path}.git',
        #          shell=True, stderr=STDOUT, cwd=None)
        
        # if run_result.returncode !=0 :
        #     raise Exception(f'Could not pull SinaraML pipeline with the name {pipeline_name}!')

    def update_sinaralib_for_pipeline(self):
        arg_parser = ArgumentParser()
        
        #arg_parser.add_argument("--git_provider_step_template_url", help="git provider base url where step template resides")    
        arg_parser.add_argument("--git_provider_organization_api", help="git provider api url in organization ")
        arg_parser.add_argument("--git_provider_organization_url", help="git provider base url in organization")

        #arg_parser.add_argument("--git_step_template_url", help="step template url")
        #arg_parser.add_argument("--step_template_nb_substep", help="the main notebook in step template")
        arg_parser.add_argument("--current_dir", help="current directory")
        #arg_parser.add_argument("--git_step_template_username", help="login to clone step template")
        #arg_parser.add_argument("--git_step_template_password", help="password to clone step template")
        
        args = arg_parser.parse_args()
        
        CURRENT_DIR = args.current_dir
        GIT_PROVIDER_URL = args.git_provider_organization_url
        GIT_PROVIDER_API = args.git_provider_organization_api

        git_provider = self.git_provider
        #git_provider = input("Please, enter your Git provider among GitHub/GitLab (default=GitLab): ") or 'GitLab'

        product_name = ''
        if git_provider == 'GitLab':
            git_provider_organization_username = input(f"Please, enter your username for managing {git_provider} repositories: ")
            git_provider_organization_password = getpass(f"Please, enter your password for managing {git_provider} repositories: ")
        
            #products_root_name = input("Please, enter your Root group for products in your organization (default=dsml_components): ") or 'dsml_components'
            product_name = input("Please, enter your Product name: ") or 'fabric_test_product'
        elif git_provider == 'GitHub':
            git_provider_organization_username = input(f"Please, enter your {git_provider} organization: ")
            git_provider_organization_password = getpass(f"Please, enter your token for managing {git_provider} repositories: ")

        
        pipeline_name = input("Please, enter your Pipeline name: ") or 'fabric_test_pipeline'

        steps_folder_glob = None
        if git_provider == 'GitLab':
            steps_folder_glob = input(f"Please, enter a glob to load '{pipeline_name}' like /some_path/steps_folder/*. (default=./product_name/pipeline_name/*): ") or f"{Path(CURRENT_DIR).resolve()}/{product_name}/{pipeline_name}/*"
        elif git_provider == 'GitHub':
            steps_folder_glob = input(f"Please, enter a glob to load '{pipeline_name}' like /some_path/steps_folder/*. (default=./pipeline_name-*): ") or f"{Path(CURRENT_DIR).resolve()}/{pipeline_name}-*"

        git_default_branch = input("Please, enter your Git default branch: ")
    
        step_folders = get_step_folders(steps_folder_glob)
            
        for step_folder in step_folders:
            step_name = None
            step_repo_git = None
            if git_provider == 'GitLab':
                step_name = Path(step_folder).name
            elif git_provider == 'GitHub':
                step_folder_split = Path(step_folder).name.split("-")
                step_name = '-'.join(step_folder_split[1::]) if len(step_folder_split) > 1 else None
    
            if step_name:
                if git_provider == 'GitLab':
                    step_repo_name = f"{step_name}"
                    #step_repo_git = f"{GIT_PROVIDER_URL}/{products_root_name}/{product_name}/{pipeline_name}/{step_repo_name}.git"
                elif git_provider == 'GitHub':
                    step_repo_name = f"{pipeline_name}-{step_name}"
                    #step_repo_git = f"{GIT_PROVIDER_URL}/{git_provider_organization_username}/{step_repo_name}.git"
                
                child_env = set_git_creds_for_subprocess(git_provider_organization_username, git_provider_organization_password)
                run_result = run(f"git checkout {git_default_branch} && \
                                   git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' submodule update --remote && \
                                   [[ $(git status | grep 'nothing to commit') ]] && echo 'Nothing to commit for now' || \
                                   (git add sinara && \
                                   git commit -m 'Updated Sinara lib' && \
                                   git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' push --set-upstream origin {git_default_branch})",
                                   universal_newlines=True,
                                   shell=True,
                                   env=child_env,
                                   stderr=STDOUT, 
                                   cwd=step_folder,
                                   executable="/bin/bash")
                
                #run_result = run (f'git remote set-url origin {step_repo_git} && \
                #                    git push -f',
                #                   shell=True, stderr=STDOUT, cwd=step_folder, executable="/bin/bash")
                if run_result.returncode !=0 :
                    raise Exception(f'Could not push a repository for SinaraML step with the name {step_repo_name}!')

    def update_origin_for_pipeline(self):
        arg_parser = ArgumentParser()
        
        arg_parser.add_argument("--git_provider_organization_api", help="git provider api url in organization ")
        arg_parser.add_argument("--git_provider_organization_url", help="git provider base url in organization")
        arg_parser.add_argument("--current_dir", help="current directory")
        arg_parser.add_argument("--new_origin_url", help="new git origin url")
        
        args = arg_parser.parse_args()
        
        CURRENT_DIR = args.current_dir
        GIT_PROVIDER_URL = args.git_provider_organization_url
        GIT_PROVIDER_API = args.git_provider_organization_api
        NEW_ORIGIN_URL = args.new_origin_url

        git_provider = self.git_provider
        #git_provider = input("Please, enter your Git provider among GitHub/GitLab (default=GitLab): ") or 'GitLab'

        product_name = ''
        if git_provider == 'GitLab':
            git_provider_organization_username = input(f"Please, enter your username for managing {git_provider} repositories: ")
            git_provider_organization_password = getpass(f"Please, enter your password for managing {git_provider} repositories: ")
        
            #products_root_name = input("Please, enter your Root group for products in your organization (default=dsml_components): ") or 'dsml_components'
            product_name = input("Please, enter your Product name: ") or 'fabric_test_product'
        elif git_provider == 'GitHub':
            git_provider_organization_username = input(f"Please, enter your {git_provider} organization: ")
            git_provider_organization_password = getpass(f"Please, enter your token for managing {git_provider} repositories: ")

        
        pipeline_name = input("Please, enter your Pipeline name: ") or 'fabric_test_pipeline'

        steps_folder_glob = None
        if git_provider == 'GitLab':
            steps_folder_glob = input(f"Please, enter a glob to load '{pipeline_name}' like /some_path/steps_folder/*. (default=./product_name/pipeline_name/*): ") or f"{Path(CURRENT_DIR).resolve()}/{product_name}/{pipeline_name}/*"
        elif git_provider == 'GitHub':
            steps_folder_glob = input(f"Please, enter a glob to load '{pipeline_name}' like /some_path/steps_folder/*. (default=./pipeline_name-*): ") or f"{Path(CURRENT_DIR).resolve()}/{pipeline_name}-*"

        git_default_branch = input("Please, enter your Git default branch: ")
    
        step_folders = get_step_folders(steps_folder_glob)
            
        for step_folder in step_folders:
            step_name = None
            step_repo_git = None
            if git_provider == 'GitLab':
                step_name = Path(step_folder).name
            elif git_provider == 'GitHub':
                step_folder_split = Path(step_folder).name.split("-")
                step_name = '-'.join(step_folder_split[1::]) if len(step_folder_split) > 1 else None
    
            if step_name:
                if git_provider == 'GitLab':
                    step_repo_name = f"{step_name}"
                    #step_repo_git = f"{GIT_PROVIDER_URL}/{products_root_name}/{product_name}/{pipeline_name}/{step_repo_name}.git"
                elif git_provider == 'GitHub':
                    step_repo_name = f"{pipeline_name}-{step_name}"
                    #step_repo_git = f"{GIT_PROVIDER_URL}/{git_provider_organization_username}/{step_repo_name}.git"
                
                child_env = set_git_creds_for_subprocess(git_provider_organization_username, git_provider_organization_password)
                run_result = run(f"git checkout {git_default_branch} && \
                                   git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' remote set-url origin {NEW_ORIGIN_URL}/{step_name}",
                                   universal_newlines=True,
                                   shell=True,
                                   env=child_env,
                                   stderr=STDOUT, 
                                   cwd=step_folder,
                                   executable="/bin/bash")
                
                #run_result = run (f'git remote set-url origin {step_repo_git} && \
                #                    git push -f',
                #                   shell=True, stderr=STDOUT, cwd=step_folder, executable="/bin/bash")
                if run_result.returncode !=0 :
                    raise Exception(f'Could not push a repository for SinaraML step with the name {step_repo_name}!')
