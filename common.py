import os
from pathlib import Path
import json
import ast

def get_sinara_user_work_dir():
    return os.getenv("JUPYTER_SERVER_ROOT") or '/home/jovyan/work'

def get_tmp_prepared():
    valid_tmp_target_path = f'/tmp/dataflow_fabric{os.getcwd().replace(get_sinara_user_work_dir(),"")}'
    os.makedirs(valid_tmp_target_path, exist_ok=True)
    tmp_path = Path('./tmp')
    if tmp_path.is_symlink():
        tmp_link = tmp_path.readlink()
        if tmp_link.as_posix() != valid_tmp_target_path:
            print("'tmp' dir is not valid, creating valid tmp dir...")
            tmp_path.unlink()                
            os.symlink(valid_tmp_target_path, './tmp', target_is_directory=True)
    else:
        if tmp_path.exists():
            print('\033[1m' + 'Current \'tmp\' folder inside your component is going to be deleted. It\'s safe, as \'tmp\' is moving to cache and will be recreated again.' + '\033[0m')
            shutil.rmtree(tmp_path)

        os.symlink(valid_tmp_target_path, './tmp', target_is_directory=True)

def get_sinaralib_url():
    sinara_org_env_var = os.getenv("SINARA_ORG")
    sinara_org = json.loads(json.dumps(ast.literal_eval(sinara_org_env_var)))
    platform_data = os.getenv("SINARA_PLATFORM").split("_")
    boundary = platform_data[1]
    platform = platform_data[-1]
    print(sinara_org["cli_bodies"])
    for cli_body in sinara_org["cli_bodies"]:
        if cli_body["boundary_name"].lower() == boundary.lower() and platform in cli_body["platform_names"]:
            return cli_body["sinara_lib"]
    return None
