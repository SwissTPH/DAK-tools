import json
import os
from fhir.resources.bundle import Bundle, BundleEntry
from fhir.resources.identifier import Identifier
from pyfhirsdc.config import get_processor_cfg, read_config_file
from pyfhirsdc.models.questionnaireSDC import QuestionnaireSDC
from pyfhirsdc.serializers.json import read_json, read_resource



from pyfhirsdc.serializers.utils import write_resource

    
    
def write_bundle(conf):
    bundle = Bundle( identifier = Identifier(value = 'EmCareBundle'),
                type  = 'collection', entry = [])
    # Read the config file
    config_obj = read_config_file(conf)
    if config_obj is None:
        exit()
    else:
        folderdir = get_processor_cfg().outputPath
        # giving file extensions
        ext = ('.json')
        # iterating over directory and subdirectory to get desired result
        for path, dirc, files in os.walk(folderdir):
            for name in files:
                if name.endswith(ext):
                    print(conf, path, dirc, name)  # printing file name
                    add_resource(path,name,bundle)
    write_resource('./bundle.json', bundle)
                    
def add_resource(path,name,bundle):
    file_path = os.path.join(path,name)
    ressource_dict = read_resource(file_path, 'any')
    if ressource_dict is not None and 'resourceType' in ressource_dict:
        
        bundle.entry.append(
            BundleEntry(
                fullUrl = ressource_dict['url'],
                resource= QuestionnaireSDC.parse_raw( read_json(file_path, type = "str")) if ressource_dict['resourceType'] == 'Questionnaire' else read_json(file_path, type = "str")
            )
        )