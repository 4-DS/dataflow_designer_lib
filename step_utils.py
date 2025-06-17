from nbconvert import NotebookExporter
import json
import nbformat
import pandas as pd
from pathlib import Path
import pprint
import glob
import os

pp = pprint.PrettyPrinter(indent=4)

def change_substep_interface(step_template_nb_name, new_substep_interface):
    
    nb_body, inputs = NotebookExporter().from_filename(step_template_nb_name)
    input_nb_dict = json.loads(nb_body)
    output_nb_dict = input_nb_dict.copy()

    #pp.pprint(input_nb_dict["cells"])
    # locate substep interface 
    for cell in input_nb_dict["cells"]:
        cell_source = cell["source"]
        if 'interface' in cell["metadata"].get("tags", []):
            #pp.pprint(cell_source)
            #print(''.join(cell_source))
            df = pd.DataFrame({'source':[''.join(cell_source)]})
            df['Values'] = df['source'].str.replace(r'substep.interface\(([^()]+)\)', new_substep_interface, regex=True)
            #print( df['Values'])
            print(''.join(df['Values']))
            cell_source_split = df['Values'].to_numpy()[0].split('\n')
            cell["source"] = [substr + '\n' for substr in cell_source_split[:-1]] + [cell_source_split[-1]]
    #pp.pprint(input_nb_dict)
    return input_nb_dict

def create_step(pipeline_name, step_repo_path, substeps, step_template_susbtep):
    substep_params = []
    for substep in substeps:
        substep_name = substep["substep_name"]
        substep_param = {
            "substep_name":f"{substep_name}.ipynb",
            "substep_params":
            {
                "param1":"None1",
                "param2":"None2"
            }
        }
        substep_params.append(substep_param)
            
        step_inputs = []
        step_outputs = []
        for step_input in substep["inputs"]:
            step_inputs.append('{ STEP_NAME: "' + step_input.get("step_name") + '", ENTITY_NAME: "' + step_input.get("entity_name") + '" },')

        for step_output in substep["outputs"]:
            step_outputs.append('{ ENTITY_NAME: "' + step_output.get("entity_name") + '" },')

        new_substep_interface = """
substep.interface(

        inputs =
        [
    {step_inputs}
        ],
        outputs = 
        [
    {step_outputs}
        ]
    )""".format(step_inputs=''.join(['            ' + step_input + '\n' for step_input in step_inputs]), step_outputs=''.join(['            ' + step_output + '\n' for step_output in step_outputs]))
        #print(new_substep_interface)

        step_template_nb_name = step_repo_path + "/" + step_template_susbtep
        step_template_nb_prepare_data = step_repo_path + "/" + 'prepare_data_for_template.ipynb'
        output_nb_dict = change_substep_interface(step_template_nb_name, new_substep_interface)
        
        step_nb_name = step_repo_path + "/" + substep_name + ".ipynb"

        nbformat.write(nbformat.from_dict(output_nb_dict), step_nb_name, 4)
        
        Path(step_template_nb_name).unlink()
        Path(step_template_nb_prepare_data).unlink()
        
    with open(f"{step_repo_path}/params/step_params.json", 'r+', encoding='utf-8') as f:
        step_params = json.load(f)

        step_params["pipeline_params"]['pipeline_name'] = pipeline_name
        step_params["substeps_params"] = substep_params
        f.seek(0)

        json.dump(step_params, f, indent=4)
        f.truncate()

def is_step(step_folder):
    params_files = glob.glob(f"{step_folder}/params/*.json")
    for step_params_file in params_files:
        with open(step_params_file, 'r') as sp:
            try:
                params = json.load(sp)
                # TODO
                # Validate a step properly by verifying presence of mandatory params
                if 'step_params' in params:
                    return True
                    #if 'step_name' in params['step_params']:
                    #    return True
            except Exception as e:
                raise Exception(f'Error reading {step_params_file}, skipping')
    return False

def get_step_folders(steps_folder_glob):
    result = []
    step_folders = glob.glob(f"{steps_folder_glob}")
    for folder in step_folders:
        if os.path.isdir(folder):
            try:
                if is_step(folder):
                    result.append(folder)
            except Exception as e:
                raise Exception(f'Cannot read step_params.json in step at {folder}, skipping step')
    return result
