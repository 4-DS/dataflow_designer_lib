import os
from pathlib import Path

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
