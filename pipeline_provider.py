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

from dataflow_designer_lib.common import get_tmp_prepared, get_sinaralib_url

pp = pprint.PrettyPrinter(indent=4)

def set_git_creds_for_subprocess(git_username, git_password):
    child_env = os.environ.copy()
    if git_username and git_password:
        child_env["GIT_USER"] = git_username
        child_env["GIT_PASSWORD"] = git_password
    return child_env

class PipelineProviderException(Exception):
    pass
    
class StepPullException(PipelineProviderException):
    pass
    
class StepPushException(PipelineProviderException):
    pass

class StepCheckoutException(PipelineProviderException):
    pass

class StepStatusException(PipelineProviderException):
    pass

class StepUpdateOriginException(PipelineProviderException):
    pass

class StepUpdateSinaraLibException(PipelineProviderException):
    pass

class StepPipelineTransferException(PipelineProviderException):
    pass

class SinaraPipelineProvider():

    def get_git_provider(self, git_provider_type):
        if git_provider_type == "GitLab":
            git_provider = importlib.import_module('dataflow_designer_lib.gitlab')
        elif git_provider_type == "GitHub":
            git_provider = importlib.import_module('dataflow_designer_lib.github')
        return git_provider

    def cache_git_creds(self, git_provider_url, git_username, git_password):
        if git_username and git_password:
            print(git_provider_url)
            print("WARNING: Git credentials are stored only plain text. It's a normal behaviour.")
            run_result = run(f"git config --global credential.helper store && \
                                   (echo url={git_provider_url}; echo username={git_username}; echo password='{git_password}'; echo ) | git credential approve",
                                     shell=True, stderr=STDOUT, cwd=None)
            if run_result.returncode != 0:
                raise Exception(f'Could not store Git credentials!')

    def get_pipeline_name(self, pipeline_dir):
        return Path(pipeline_dir).stem

    def get_step_name(self, step_folder, git_provider_type):
        if git_provider_type == "GitLab":
            step_name = Path(step_folder).name
        elif git_provider_type == "GitHub":
            step_folder_split = Path(step_folder).name.split("-")
            step_name = "-".join(step_folder_split[1::]) if len(step_folder_split) > 1 else None
        return step_name

    def get_step_repo_name(self, step_name, pipeline_name, git_provider_type):
        if git_provider_type == 'GitLab':
            return f"{step_name}"
        elif git_provider_type == 'GitHub':
            return f"{pipeline_name}-{step_name}"

    def get_steps_folder_glob(self, git_provider_type, pipeline_dir, pipeline_name):
        if git_provider_type == "GitLab":
            steps_folder_glob = f"{Path(pipeline_dir).resolve()}/*"
        elif git_provider_type == "GitHub":
            steps_folder_glob = f"{Path(pipeline_dir).resolve()}/{pipeline_name}-*"
        else:
            raise Exception(f"Unsupported git provider {git_provider_type}")
        return steps_folder_glob

    def create_pipeline(self, pipeline_manifest_path, pipeline_dir, pipeline_name,
                        git_provider, git_default_branch = "main",
                        git_step_template_url = None, step_template_nb_substep = None, git_step_template_username = None, git_step_template_password = None,
                        git_username = None, git_useremail = None):

        git_provider_url = urlparse(git_step_template_url)
        git_provider_url = f"{git_provider_url.scheme}://{git_provider_url.netloc}"
        self.cache_git_creds(git_step_template_url, git_username, git_step_template_password)
        
        with open(pipeline_manifest_path) as f:
            p_manifest_dict = yaml.safe_load(f)

        pipeline_dir = pipeline_dir + "/" + pipeline_name
        os.makedirs(pipeline_dir, exist_ok=True)
            
        for step in p_manifest_dict["steps"]:
            step_name = step["step_name"]
 
            step_repo_name = ""
            if git_provider == "GitLab":
                step_repo_name = f"{step_name}"
            elif git_provider == "GitHub":
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
        
            if run_result.returncode != 0:
                raise Exception(f'Could not prepare a repository for SinaraML step with the name {step_repo_name}!')

            print(f'pipeline_name {pipeline_name} step_repo_path: {step_repo_path} step["substeps"]: {step["substeps"]} step_template_nb_substep: {step_template_nb_substep}')
            create_step(pipeline_name, step_repo_path, step["substeps"], step_template_nb_substep)

    def push_pipeline(self, pipeline_dir, pipeline_git_url,
                      git_provider_type, git_provider_url, git_provider_api,
                      git_default_branch = "main",
                      git_username = None, git_password = None):
        self.cache_git_creds(git_provider_url, git_username, git_password)

        steps_folder_glob = f"{pipeline_dir}/*"
        step_folders = get_step_folders(steps_folder_glob)

        git_provider = self.get_git_provider(git_provider_type)
        gitlab_session = None

        if pipeline_git_url is None or pipeline_git_url == "None": # get pipeline git url from first pipeline step
            pipeline_git_url = None
            for step_repo_name in get_step_folders(f"{pipeline_dir}/*"):
                import subprocess
                result = subprocess.run(f"cd {step_repo_name} && git config --get remote.origin.url", shell=True, stdout=subprocess.PIPE)
                step_git_url = result.stdout.decode("utf-8").replace("\n", "")
                if not step_git_url is None:
                    pipeline_git_url = step_git_url
                    break
            if pipeline_git_url is None:
                raise StepPushException(f"Could not push SinaraML pipeline: git repository not found!")
            parsed = urlparse(pipeline_git_url)
            lst = parsed.path.split("/")
            git_folder = "/".join(lst[:len(lst)-1]) # remove step name from path
            if git_provider_type == "GitLab":
                pass
            elif git_provider_type == "GitHub":
                git_folder = git_folder + "/" + lst[-1].split["-"][0] # add pipeline name
            url_parts = [parsed.scheme, parsed.netloc, git_folder, "", "", ""]
            pipeline_git_url = urlunparse(url_parts)

        
        pipeline_name = self.get_pipeline_name(pipeline_dir)

        if git_provider_type == "GitLab":
            gitlab_session = git_provider.get_gitlab_session(git_provider_url, git_username, git_password)

            pipeline_group_path = urlparse(pipeline_git_url).path[1::] # remove root slash
            pipeline_name_id = git_provider.get_gitlab_group_id2(git_provider_api, gitlab_session, pipeline_group_path)
            print(pipeline_name_id)

        print(f"You are about co push following steps to to the {git_provider_url} repo:")
        for step_folder in step_folders:
            print(step_folder)
        yes = input("Continue? (Y/n):")
        if yes and not yes.lower().startswith("y"):
            return

        for step_folder in step_folders:
            step_name = None
            step_name = self.get_step_name(step_folder, git_provider_type)
            step_repo = self.get_step_repo_name(step_name, pipeline_name, git_provider_type)
    
            if step_name:
                step_origin_url = None
                response = None
                if git_provider_type == "GitLab":
                    # create GitLab repo for a step
                    response = git_provider.create_gitlab_repo(git_provider_api=git_provider_api,
                                                                gitlab_session=gitlab_session,
                                                                repo_group_id=pipeline_name_id,
                                                                repo_name=step_repo,
                                                                repo_description="This is your " + step_name + " step in pipeline " + pipeline_name,
                                                                is_private=True)
                    
                    step_origin_url = git_provider.get_gitlab_project_url(git_provider_api=git_provider_api,
                                                             gitlab_session=gitlab_session,
                                                             group_id=pipeline_name_id,
                                                             project_name=step_repo)
                elif git_provider_type == "GitHub":               
                    git_org_name = urlparse(pipeline_git_url).path.split("/")[1]
                    if not git_provider.check_github_project_exists(git_provider_api=git_provider_api,
                                                                    org_name=git_org_name,
                                                                    token=git_password,
                                                                    repo_name=step_repo):
                        # create GitHub repo for a step
                        response = git_provider.create_github_repo(git_provider_api=git_provider_api,
                                                                   git_provider_url=git_provider_url,
                                                                   org_name=git_org_name,
                                                                   token=git_password,
                                                                   repo_name=step_repo,
                                                                   repo_description="This is your " + step_name + " step in pipeline " + pipeline_name,
                                                                   is_private=True)
                    if not step_origin_url:
                        step_origin_url = response.json()["clone_url"] if response else \
                            git_provider.get_github_project_url(git_provider_api=git_provider_api,
                                                                org_name=git_org_name,
                                                                token=git_password,
                                                                repo_name=step_repo)
                
                child_env = set_git_creds_for_subprocess(git_username, git_password)
                run_result = run(f"git checkout {git_default_branch} && \
                                   git remote set-url origin {step_origin_url} && \
                                   ([[ $(git ls-remote --exit-code --heads origin refs/heads/{git_default_branch}) ]] && echo 'Pulling new changes' && \
                                   git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' pull --set-upstream origin {git_default_branch}); \
                                   (echo 'Pushing new' && git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' push --set-upstream origin {git_default_branch})",
                                   universal_newlines=True,
                                   shell=True,
                                   env=child_env,
                                   stderr=STDOUT, 
                                   cwd=step_folder,
                                   executable="/bin/bash")

                if run_result.returncode != 0:
                    raise Exception(f"Could not push a repository for SinaraML step with the name {step_name}!")

    def pull_pipeline(self, pipeline_dir, pipeline_git_url,
                      git_provider_type, git_provider_url, git_provider_api,
                      git_default_branch = "main",
                      git_username = None, git_password = None):

        do_clone = True
        if pipeline_git_url is None or pipeline_git_url == "None": # get pipeline git url from first pipeline step
            pipeline_git_url = None
            do_clone = False
            for step_repo_name in get_step_folders(f"{pipeline_dir}/*"):
                import subprocess
                print(f"checking step {step_repo_name}")
                result = subprocess.run(f"cd {step_repo_name} && git config --get remote.origin.url", shell=True, stdout=subprocess.PIPE)
                step_git_url = result.stdout.decode("utf-8").replace("\n", "")
                if not step_git_url is None:
                    pipeline_git_url = step_git_url
                    break
            if pipeline_git_url is None:
                raise StepPullException(f"Could not pull SinaraML pipeline: git repository not found!")

            parsed = urlparse(step_git_url)
            lst = parsed.path.split("/")
            git_folder = "/".join(lst[:len(lst)-1]) # remove step name from path
            if git_provider_type == "GitLab":
                pass
            elif git_provider_type == "GitHub":
                git_folder = git_folder + "/" + lst[-1].split["-"][0] # add pipeline name
            url_parts = [parsed.scheme, parsed.netloc, git_folder, "", "", ""]
            pipeline_git_url = urlunparse(url_parts)
        
        git_provider = self.get_git_provider(git_provider_type)
        pipeline_name = ""
        
        gitlab_session = None
        step_list = []
        if git_provider_type == "GitLab":
            gitlab_session = git_provider.get_gitlab_session(git_provider_url, git_username, git_password)
            pipeline_group_path = urlparse(pipeline_git_url).path[1::]
            step_list = git_provider.get_gitlab_group_projects(git_provider_api, gitlab_session, pipeline_group_path)
            pipeline_name = urlparse(pipeline_git_url).path.split("/")[-1]

        elif git_provider_type == 'GitHub':

            git_org_name = urlparse(pipeline_git_url).path.split("/")[1]
            print(git_org_name)
            pipeline_name = urlparse(pipeline_git_url).path.split("/")[-1].split["-"][0]
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
                    raise Exception(f"Could not pull SinaraML pipeline {pipeline_name}: folder already exists!")
                else:
                    raise  # raises the error again

        for step in step_list:
            step_repo_name = step["step_repo_name"]
            step_repo_git = step["step_repo_git"]
            if do_clone:
                # clone
                git_command = f"clone --recursive {step_repo_git}"
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

    def update_sinaralib_for_pipeline(self,
                          pipeline_dir,
                          git_provider_type,
                          git_provider_url,
                          git_provider_api,
                          steps_folder_glob = None,
                          git_username = None,
                          git_password = None
                          ):
        step_update_sinaralib_cmd = f"git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' submodule update --remote && \
                                   [[ $(git status | grep 'nothing to commit') ]] && echo 'Nothing to commit for now' || \
                                   (git add sinara && \
                                   git commit -m 'Updated Sinara lib' && \
                                   git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' push --set-upstream origin main)"
        try:
            self.exec_command_for_each_step(pipeline_dir = pipeline_dir,
                              git_provider_type = git_provider_type,
                              #git_provider_url = git_provider_url,
                              #git_provider_api = git_provider_api,
                              steps_folder_glob = steps_folder_glob,
                              git_username = git_username,
                              git_password = git_password,
                              step_cmd = step_update_sinaralib_cmd)
        except Exception as e:
            (ex,) = e.args
            raise StepUpdateSinaraLibException(f"Could not update sinara library in the repository for SinaraML step {ex['step_name']} at {ex['step_folder']}!")
    
    def update_origin_for_pipeline(self,
                          pipeline_dir,
                          git_provider_type,
                          git_provider_url,
                          git_provider_api,
                          steps_folder_glob = None,
                          git_username = None,
                          git_password = None,
                          new_origin_url = None):
        try:
            pipeline_name = self.get_pipeline_name(pipeline_dir)
            if not steps_folder_glob:
                steps_folder_glob = self.get_steps_folder_glob(git_provider_type, pipeline_dir, pipeline_name)
            step_folders = get_step_folders(steps_folder_glob)
                
            for step_folder in step_folders:
                step_name = None
                step_name = self.get_step_name(step_folder, git_provider_type)
                step_repo = self.get_step_repo_name(step_name, pipeline_name, git_provider_type)
                child_env = set_git_creds_for_subprocess(git_username, git_password)
                step_cmd = f"git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' remote set-url origin {new_origin_url}/{step_repo}"
                run_result = run(
                    step_cmd,
                    universal_newlines=True,
                    shell=True,
                    check=True,
                    capture_output=True,
                    env=child_env,
                    text=True,
                    cwd=step_folder,
                    executable="/bin/bash")

        except Exception as e:
            raise StepUpdateOriginException(f"Could not update origin in the repository for SinaraML step {step_name} at {step_folder}!")

    def checkout_pipeline(self,
                          pipeline_dir,
                          git_provider_type,
                          git_provider_url,
                          git_provider_api,
                          git_branch = 'main',
                          steps_folder_glob = None,
                          git_username = None,
                          git_password = None
                          ):
        step_checkout_cmd = f"git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' checkout -f {git_branch}"
        try:
            self.exec_command_for_each_step(pipeline_dir = pipeline_dir,
                              git_provider_type = git_provider_type,
                              #git_provider_url = git_provider_url,
                              #git_provider_api = agit_provider_api,
                              steps_folder_glob = steps_folder_glob,
                              git_username = git_username,
                              git_password = git_password,
                              step_cmd = step_checkout_cmd)
        except Exception as e:
            (ex,) = e.args
            raise StepCheckoutException(f"Could not checkout branch {git_branch} in the repository for SinaraML step {ex['step_name']} at {ex['step_folder']}!")

    def pipeline_status(self, pipeline_dir, git_provider_type):
        git_status_cmd = f"git status"
        try:
            self.exec_command_for_each_step(pipeline_dir = pipeline_dir,
                              git_provider_type = git_provider_type,
                              #git_provider_url = git_provider_url,
                              #git_provider_api = agit_provider_api,
                              #steps_folder_glob = steps_folder_glob,
                              #git_username = git_username,
                              #git_password = git_password,
                              step_cmd = git_status_cmd)
        except Exception as e:
            (ex,) = e.args
            raise StepStatusException(f"Could not get status in the repository for SinaraML step {ex['step_name']} at {ex['step_folder']}!")

    def pipeline_transfer(self,
                          pipeline_dir,
                          git_provider_type,
                          git_provider_url,
                          git_provider_api,
                          steps_folder_glob = None,
                          git_username = None,
                          git_password = None,
                          new_origin_url = None):
        try:
            pipeline_name = self.get_pipeline_name(pipeline_dir)
            if not steps_folder_glob:
                steps_folder_glob = self.get_steps_folder_glob(git_provider_type, pipeline_dir, pipeline_name)
            step_folders = get_step_folders(steps_folder_glob)

            new_sinaralib_url = get_sinaralib_url()
                
            for step_folder in step_folders:
                step_name = None
                step_name = self.get_step_name(step_folder, git_provider_type)
                step_repo = self.get_step_repo_name(step_name, pipeline_name, git_provider_type)
                child_env = set_git_creds_for_subprocess(git_username, git_password)
                step_cmd = f"git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' remote set-url origin {new_origin_url}/{step_repo}"
                submodule_cmd = f"git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' submodule set-url sinara {new_sinaralib_url} && git submodule sync --recursive && cd sinara && git checkout main && git -c credential.helper=\'!f() {{ sleep 1; echo \"username=${{GIT_USER}}\"; echo \"password=${{GIT_PASSWORD}}\"; }}; f\' pull"
                run_result = run(
                    step_cmd,
                    universal_newlines=True,
                    shell=True,
                    check=True,
                    capture_output=True,
                    env=child_env,
                    text=True,
                    cwd=step_folder,
                    executable="/bin/bash")
                
                run_result = run(
                    submodule_cmd,
                    universal_newlines=True,
                    shell=True,
                    check=True,
                    capture_output=True,
                    env=child_env,
                    text=True,
                    cwd=step_folder,
                    executable="/bin/bash")

        except Exception as e:
            raise StepPipelineTransferException(f"Could not transfer repository for SinaraML step {step_name} at {step_folder}!")
    
    def exec_command_for_each_step(self,
                          pipeline_dir,
                          git_provider_type,
                          #git_provider_url,
                          #git_provider_api,
                          steps_folder_glob = None,
                          git_username = None,
                          git_password = None,
                          step_cmd = None):
        pipeline_name = self.get_pipeline_name(pipeline_dir)

        if not steps_folder_glob:
            steps_folder_glob = self.get_steps_folder_glob(git_provider_type, pipeline_dir, pipeline_name)
        print(steps_folder_glob)

        step_folders = get_step_folders(steps_folder_glob)
            
        for step_folder in step_folders:
            step_name = None
            step_name = self.get_step_name(step_folder, git_provider_type)
            child_env = set_git_creds_for_subprocess(git_username, git_password)
            print(f"\033[1mStep: {step_name}\033[0m")
            run_result = run(
                step_cmd,
                universal_newlines=True,
                shell=True,
                check=True,
                capture_output=False,
                env=child_env,
                text=True,
                cwd=step_folder,
                executable="/bin/bash")

            if run_result.returncode != 0:
                raise Exception({"step_name": step_name, "step_folder": step_folder})
