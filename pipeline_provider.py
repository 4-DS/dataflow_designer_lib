import requests

import json
import yaml
from pathlib import Path
from subprocess import STDOUT, run, call
import os

import re
import sys
import requests
from getpass import getpass
from argparse import ArgumentParser

from .step_utils import create_step, get_step_folders
from dataflow_designer_lib.github import create_github_repo
from dataflow_designer_lib.gitlab import *

import importlib

class SinaraPipelineProvider():

    def create_pipeline(pipeline_manifest_path):

        _pipeline_manifest_path = str(Path(__file__).parent.parent.resolve()) + '/' + pipeline_manifest_path

        print(f'Trying pipeline manifest in {_pipeline_manifest_path}')

        arg_parser = ArgumentParser()
        
        #arg_parser.add_argument("--git_provider_step_template_url", help="git provider base url where step template resides")    
        arg_parser.add_argument("--git_provider_organization_api", help="git provider api url in organization ")    
        arg_parser.add_argument("--git_provider_organization_url", help="git provider base url in organization")

        arg_parser.add_argument("--git_step_template_url", help="step template url")
        arg_parser.add_argument("--step_template_nb_substep", help="the main notebook in step template")
        arg_parser.add_argument("--current_dir", help="current directory")      
        arg_parser.add_argument("--git_step_template_username", help="login to clone step template")
        arg_parser.add_argument("--git_step_template_password", help="password to clone step template")
        
        args = arg_parser.parse_args()
        
        SNR_STEP_TEMPLATE = args.git_step_template_url
        SNR_STEP_TEMPLATE_SUBSTEP = args.step_template_nb_substep
        CURRENT_DIR = args.current_dir
        
        git_public_user_sent = args.git_step_template_username is not None and args.git_password
        if git_public_user_sent:
            GIT_STEP_TEMPLATE_USERNAME = args.git_step_template_username
            GIT_STEP_TEMPLATE_PASSWORD = args.git_password

        git_provider = input("Please, enter your Git provider among GitHub/GitLab (default=GitLab): ") or 'GitLab'
        product_name = None
        if git_provider == 'GitLab':
            product_name = input("Please, enter your Product name: ") or 'fabric_test_product'
        elif git_provider == 'GitHub':
            pass
        
        pipeline_name = input("Please, enter your Pipeline name: ") or 'fabric_test_pipeline'
        pipeline_folder = input(f"Please, enter a folder to save '{pipeline_name}': ") or str(Path(CURRENT_DIR).resolve())
        
        git_username = input("Please, enter your Git user name (default=data_scientist_name): ") or "data_scientist_name"
        git_useremail = input("Please, enter your Git user email (default=data_scientist_name@example.com): ") or "data_scientist_name@example.com"
        
        with open(_pipeline_manifest_path) as f:
            p_manifest_dict = yaml.safe_load(f)

        if git_provider == 'GitLab':
            pipeline_folder = pipeline_folder + '/'+ product_name + '/' + pipeline_name
            os.makedirs(pipeline_folder, exist_ok=True)
            
        for step in p_manifest_dict["steps"]:
            step_name = step["step_name"]
 
            step_repo_name = ''
            if git_provider == 'GitLab':
                step_repo_name = f"{step_name}"
            elif git_provider == 'GitHub':
                step_repo_name = f"{pipeline_name}-{step_name}"
                
            step_repo_path = pipeline_folder + "/" + step_repo_name + "/"

            run_result = None
            if git_public_user_sent:

                run_result = run(f"rm -rf {step_repo_name} && \
                                   git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' clone --recursive {SNR_STEP_TEMPLATE} {step_repo_name} && \
                                   cd {step_repo_name} && \
                                   git config user.email {git_useremail} && \
                                   git config user.name {git_username}",
                                   universal_newlines=True,
                                   shell=True,
                                   env={
                                        "GIT_USER": GIT_STEP_TEMPLATE_USERNAME,
                                        "GIT_PASSWORD": GIT_STEP_TEMPLATE_PASSWORD
                                   },
                                   stderr=STDOUT, 
                                   cwd=pipeline_folder, 
                                   executable="/bin/bash")
                                     
            else:
                run_result = run(f'rm -rf {step_repo_name} && \
                               git clone --recurse-submodules {SNR_STEP_TEMPLATE} {step_repo_name} && \
                               cd {step_repo_name} && \
                               git config user.email "{git_useremail}" && \
                               git config user.name "{git_username}"', 
                             shell=True, stderr=STDOUT, cwd=pipeline_folder, executable="/bin/bash")
        
            if run_result.returncode !=0 :
                raise Exception(f'Could not prepare a repository for SinaraML step with the name {step_repo_name}!')
                     
            create_step(pipeline_name, step_repo_path, step["substeps"], SNR_STEP_TEMPLATE_SUBSTEP)
        
            run_result = run (f'git add -A && \
                                git commit -m "Adjust substep interface and step parameters" && \
                                git reset $(git commit-tree HEAD^{{tree}} -m "a new SinaraML step")',
                                shell=True, stderr=STDOUT, cwd=step_repo_path, executable="/bin/bash")
            if run_result.returncode !=0 :
                raise Exception(f'Could not prepare a repository for SinaraML step with the name {step_repo_name}!')

    def push_pipeline():
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
          
        git_provider = input("Please, enter your Git provider among GitHub/GitLab (default=GitLab): ") or 'GitLab'

        product_name = ''
        if git_provider == 'GitLab':
            git_provider_organization_username = getpass(f"Please, enter your username for managing {git_provider} repositories: ")
            git_provider_organization_password = getpass(f"Please, enter your password for managing {git_provider} repositories: ")
        
            products_root_name = input("Please, enter your Root group for products in your organization (default=dsml_components): ") or 'dsml_components'
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

        save_git_creds = input(f"Would you like to store Git credentials once? WARNING: Currenly, only plain text is supported. y/n (default=y): ") or "y"
        
        if save_git_creds == "y":
            run_result = run(f"git config --global credential.helper store && \
                               (echo url={GIT_PROVIDER_URL}; echo username={git_provider_organization_username}; echo password={git_provider_organization_password}; echo ) | git credential approve",
                                 shell=True, stderr=STDOUT, cwd=None)
        
            if run_result.returncode !=0 :
                raise Exception(f'Could not store Git credentials!')
        
        step_folders = get_step_folders(steps_folder_glob)

        gitlab_session = None
        if git_provider == 'GitLab':
            gitlab_session = get_gitlab_session(GIT_PROVIDER_URL, git_provider_organization_username, git_provider_organization_password)
            products_root_name_id = get_gitlab_group_id(GIT_PROVIDER_API, gitlab_session, products_root_name)
            print(products_root_name_id)
            product_name_id = create_gitlab_group(GIT_PROVIDER_API, gitlab_session, product_name, products_root_name_id)
            print(product_name_id)
            pipeline_name_id = create_gitlab_group(GIT_PROVIDER_API, gitlab_session, pipeline_name, product_name_id)
            print(pipeline_name_id)
            
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
                    step_repo_git = f"{GIT_PROVIDER_URL}/{products_root_name}/{product_name}/{pipeline_name}/{step_repo_name}.git"
                    # create GitLab repo for a step

                    response = create_gitlab_repo(git_provider_api=GIT_PROVIDER_API, gitlab_session=gitlab_session, repo_group_id=pipeline_name_id, repo_name=step_repo_name, repo_description='This is your ' + step_name + ' step in pipeline ' + pipeline_name, is_private=True)
              
                elif git_provider == 'GitHub':
                    step_repo_name = f"{pipeline_name}-{step_name}"
                    step_repo_git = f"{GIT_PROVIDER_URL}/{git_provider_organization_username}/{step_repo_name}.git"
                    # create GitHub repo for a step
                    response = create_github_repo(git_provider_api=GIT_PROVIDER_API, git_provider_url=GIT_PROVIDER_URL, org_name=git_provider_organization_username, token=git_provider_organization_password, repo_name=step_repo_name, repo_description='This is your ' + step_name + ' step in pipeline ' + pipeline_name, is_private=True)
              
                run_result = run (f'git remote set-url origin {step_repo_git} && \
                                    git push -f',
                                   shell=True, stderr=STDOUT, cwd=step_folder, executable="/bin/bash")
                if run_result.returncode !=0 :
                    raise Exception(f'Could not create a repository for SinaraML step with the name {step_repo_name}!')
