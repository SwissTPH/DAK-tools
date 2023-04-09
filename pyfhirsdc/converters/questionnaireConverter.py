
import json
import logging

import pandas as pd
from pyfhirsdc.config import get_processor_cfg, get_defaut_fhir

from pyfhirsdc.converters.mappingConverter import (get_questionnaire_mapping, add_mapping_url)
from pyfhirsdc.converters.questionnaireItemConverter import (
    get_clean_html, get_question_extension, get_question_fhir_data_type,get_question_valueset,get_question_answeroption,
    get_question_repeats,get_question_definition, get_timestamp_item, get_display,
    get_type_details, get_initial_value,get_disabled_display  )
from pyfhirsdc.converters.utils import clean_name, get_resource_url, inject_sub_questionnaires
from pyfhirsdc.serializers.http import post_files
from pyfhirsdc.serializers.librarySerializer import generate_attached_library
from pyfhirsdc.serializers.utils import get_resource_path, write_resource
from pyfhirsdc.converters.extensionsConverter import (get_variable_extension,get_popup_ext,get_help_ext, get_instruction_ext)
from pyfhirsdc.models.questionnaireSDC import (QuestionnaireItemSDC,
                                               QuestionnaireSDC)    
logger = logging.getLogger("default")

## generate questinnaire and questionnaire response
def generate_questionnaire( name ,df_questions) :
    
    # try to load the existing questionnaire
    fullpath = get_resource_path("Questionnaire", name)
    logger.info('processing questionnaire {0}'.format(name))
    # read file content if it exists
    questionnaire = init_questionnaire(fullpath, name)
    # clean the data frame
    
    
    df_questions = inject_sub_questionnaires(df_questions)
    df_questions_item = df_questions[df_questions.type != 'mapping']
    df_questions_lib = df_questions
    # add the fields based on the ID in linkID in items, overwrite based on the designNote (if contains status::draft)
    questionnaire = convert_df_to_questionitems(questionnaire, df_questions_item)
        # add timestamp
    questionnaire.item.append(get_timestamp_item())
    #### StructureMap ####
    

    #structure_maps = get_structure_map_bundle(name, df_questions)
    #structure_maps = get_structure_maps(name, df_questions)
    mapping = get_questionnaire_mapping(name, df_questions_lib)
    questionnaire = add_mapping_url(questionnaire, mapping)
    library = generate_attached_library(questionnaire,df_questions_lib,'q')

    # write file
    write_resource(fullpath, questionnaire, get_processor_cfg().encoding)
    #CQL files 
    if get_processor_cfg().fhirpath_validator is not None:
        post_files(fullpath, get_processor_cfg().fhirpath_validator)
    

def init_questionnaire(filepath, id):
    #commented to force re-generation questionnaire_json = read_resource(filepath, "Questionnaire")
    questionnaire_json = None
    default =get_defaut_fhir('Questionnaire')
    if questionnaire_json is not None :
        questionnaire = QuestionnaireSDC.parse_raw( json.dumps(questionnaire_json))  
    elif default is not None:
        # create file from default
        questionnaire = QuestionnaireSDC.parse_raw( json.dumps(default))
        questionnaire.id=clean_name(id)
        questionnaire.title=id
        questionnaire.name=id
        questionnaire.url=get_resource_url('Questionnaire',id) 

    return questionnaire

def convert_df_to_questionitems(ressource,df_questions, parentId = None):
    # create a dict to iterate
    if parentId is None:
        if 'parentId' in df_questions:
            dict_questions = df_questions[df_questions.parentId.isna()].to_dict('index')
        else:
            dict_questions = df_questions.to_dict('index')
    else:
        if 'parentId' in df_questions:
            dict_questions = df_questions[df_questions.parentId == parentId ].to_dict('index')
        else:
            return ressource
    # Use first part of the id (before DE) as an ID
    # questionnaire.id = list(dict_questions.keys())[0].split(".DE")[0]
    # delete all item in case of overwrite strategy
    for  question in dict_questions.values():
        # manage group
        type, detail_1, detail_2 = get_type_details(question)
        if type is None:
            if pd.notna(question['id']): logger.warning("${0} is not a valid type, see question ${1}".format(question['type'], question['id']))       
        elif type == "skipped":
            pass
        # for multiline variables
        elif  type == 'variable':
            variable = get_variable_extension(question['id'],question['calculatedExpression'],df_questions)
            if variable is not None:
                ressource.extension.append(variable)
        else:
            process_quesitonnaire_line(ressource, question['id'], question,df_questions )


    # close all open groups


    return ressource
# per activity definition 
# ## title
# check the initialExpression

def get_activity_inputs(df_questionnaire):
    
  
  pass

def get_activity_ouputs(df_questionnaire):
  # check if there is Patient, Encounter, Task, Observation, Condition
  # in case helpers retrive the details
  
  pass
def process_quesitonnaire_line(resource, id, question, df_questions):
    type =get_question_fhir_data_type(question['type'])
    if pd.notna(question['required']):
        if int(question['required']) == 1:
            question['required']=1
        else : question['required']=0
    else : question['required']=0
    if type is not None:
        new_question = QuestionnaireItemSDC(
                    linkId = id,
                    type = type,
                    required= question['required'],
                    extension = get_question_extension(question, id, df_questions),
                    answerValueSet = get_question_valueset(question),
                    answerOption=get_question_answeroption(question, id, df_questions ),
                    repeats= get_question_repeats(question),
                    #design_note = "status::draft",
                    definition = get_question_definition(question),
                    initial = get_initial_value(question),
                    readOnly = get_disabled_display(question)
                )

        if pd.notna(question['label']) and question['type'] != "select_boolean":
            #textile create html text
            # remove the leanding \t<p> and following </p>
            new_question.text = get_clean_html(question['label'])
        display = get_display(question)
        if 'help' in question and pd.notna(question['help']) and len(question['help'])>0 :
            if new_question.item is None:
                new_question.item = []
            html = get_clean_html(question['help']) 
            help = QuestionnaireItemSDC(
                    linkId = question['id']+"-help",
                    type= 'display',
                    text = html,
                    extension = [get_help_ext()],
            )
            if 'help-popup' in display:
                help.extension.append(get_popup_ext())
            new_question.item.append(help)   
            # add instruction in case there is no text, sdc defect don't show the help if no text
            if new_question.text == None:
                new_question.item.append( QuestionnaireItemSDC(
                    linkId = question['id']+"-instruction",
                    type= 'display',
                    text = 'help',
                    extension = [get_instruction_ext()],
                ))   
        #TODO  workarround for https://github.com/google/android-fhir/issues/1550
        #unit = get_unit(display)
        #if unit is not None:   
        #    if new_question.item is None:
        #        new_question.item = []
        #    new_question.item.append( QuestionnaireItemSDC(
        #            linkId = question['id']+"-unit",
        #            type= 'display',
        #            text = unit,
        #            extension = [get_security_ext()],
        #        )) 
        #ENDTODO
        if 'parentId' in  df_questions:
            convert_df_to_questionitems(new_question,df_questions, id )
                    
        # we save the question as a new ressouce
        if resource.item is None:
            resource.item = []

        resource.item.append(new_question)             
        return new_question
    
# per activity definition 
# ## title
# check the initialExpression

def get_questionnaire_inputs(df_questionnaire):
    
  
  pass

