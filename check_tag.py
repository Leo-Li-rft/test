import pprint
import argparse
import re
import os.path, os, sys
from enum import Enum

# regular expression for variable.tf
DEFAULT_TAGS_VAR_PATTERN = r'^\s*variable\s+"default_tags"\s*{\s*$'
NORMAL_VAR_PATTERN = r'^\s*variable\s+"(?!default_tags).*"\s*{\s*$'
MANDATORY_TAGS = ["tr:financial-identifier","tr:application-asset-insight-id","tr:environment-type","tr:service-name","tr:resource-owner"]
MANDATORY_TAGS_PATTERN = '^[^"]*"('+"|".join(MANDATORY_TAGS)+')"\s*:\s*"[^"]*"\s*$'

# regular expression for xxx.tf
RESOURCE_PATTERN = r'^\s*resource\s*"([^"]*)"\s*"([^"]*)"\s*{\s*$'
TAG_IN_RESOURCE_PATTERN = r'^\s*tags\s*=\s*var\.default_tags\s*$'
DATA_OR_PROVIDER_PATTERN = r'^\s*(provider|data)\s*(?:\s*"[^"]*"\s*){1,2}$'
VAR_FILE_NAME = 'variable.tf'


class ValidResourceType(Enum):
	aws_efs_file_system = 1
	aws_iam_role = 2
	aws_ecs_task_definition = 3
	aws_sqs_queue = 4
	aws_ecs_service = 5
	aws_ecs_cluster = 6
	aws_lambda_function = 7
	aws_sns_topic = 8
	aws_dynamodb_table = 9

def error_exit(msg):
	print(msg)
	sys.exit(1)

def ok_exit():
	print('Everything is ok')
	sys.exit(1)

def parse_arguments():
	ap = argparse.ArgumentParser()
	ap.add_argument('foldername', help='the terraform file folder')
	args = vars(ap.parse_args())
	return args

def is_valid_resource(resource_type):
	resource_type = resource_type.lower()
	if resource_type in ValidResourceType.__members__:
		return True
	return False

def is_valid_var_tf(file):
	in_default_tags_variable = False
	mandatory_tags_dict = {}
	missing_tags = []
	status = True
	msg = 'All mandatory tags are defined'
	with open(file) as f:
		for line in f:
			if re.match(DEFAULT_TAGS_VAR_PATTERN,line):
				in_default_tags_variable = True
				continue
			elif re.match(NORMAL_VAR_PATTERN,line):
				in_default_tags_variable = False
				break
			if in_default_tags_variable:
				m = re.match(MANDATORY_TAGS_PATTERN,line)
				if m:
					mandatory_tags_dict[m.group(1)] = 1
	for tag in MANDATORY_TAGS:
		if tag not in mandatory_tags_dict:
			missing_tags.append(tag)
	if missing_tags:
		msg = 'Error: file ['+file+'] tag['+",".join(missing_tags)+'] are not defined'
		status = False
	return (status, msg)

def is_valid_normal_tf(file):
	in_resource, has_tags, status = False, False, True
	resource_type, resource_name = None, None
	resource_missing_tags = []
	invalid_resource_with_tags = []
	msg = 'All rsources have tags defined'

	with open(file) as f:
		for line in f:
			m = re.match(RESOURCE_PATTERN,line)
			if m:
				if resource_type is not None:
					if is_valid_resource(resource_type) and not has_tags:
						msg = 'Error: resource['+resource_name+'] does not have mandatory tags'
						status = False
					elif not is_valid_resource(resource_type) and has_tags:
						msg = 'Error: resource['+resource_name+'] should not have tags'
						status = False
				resource_type = m.group(1)
				resource_name = m.group(2)
				in_resource = True
				has_tags = False
				continue
			if re.match(DATA_OR_PROVIDER_PATTERN,line):
				in_resource = False
				continue
			if re.match(TAG_IN_RESOURCE_PATTERN,line) and in_resource:
				has_tags = True
	if resource_type is not None:
		if is_valid_resource(resource_type) and not has_tags:
			resource_missing_tags.append(resource_name)
			status = False
		elif not is_valid_resource(resource_type) and has_tags:
			invalid_resource_with_tags.append(resource_name)
			status = False

	if not status:
		msg = 'Error: file['+file+'] '
		if resource_missing_tags:
			msg = msg +'resources['+",".join(resource_missing_tags)+'] missed tags '
		if invalid_resource_with_tags:
			msg = msg +'resources['+",".join(invalid_resource_with_tags)+'] should not have tags'
	return(status, msg)

def check_tf_file(folder_path):
	final_status = True
	msgs = []
	for root, dirs, files in os.walk(folder_path):
		tf_files = []
		has_var_tf = VAR_FILE_NAME in files and True or False
		root = root.replace("\\","/")
		for file in files:
			if file.endswith(".tf") and file != VAR_FILE_NAME:
				has_tf = True
				tf_file = "/".join([root,file])
				tf_files.append(tf_file)
		if has_tf and not has_var_tf:
			msg = 'Error: for folder ['+root+'], there is .tf file but not '+VAR_FILE_NAME+' file'
			#error_exit(msg)
			final_status = False
			msgs.append(msg)
		elif has_tf and has_var_tf:
			var_tf_file = root+"/"+VAR_FILE_NAME
			status, msg = is_valid_var_tf(var_tf_file)
			if final_status and not status:
				final_status = status
			if not status:
				msgs.append(msg)
			# if not status:
			# 	error_exit(msg)
			for normal_tf_file in tf_files:
				status, msg = is_valid_normal_tf(normal_tf_file)
				if final_status and not status:
					final_status = status
				if not status:
					msgs.append(msg)
				# if not status:
				# 	error_exit(msg)
	if not final_status:
		final_msg = "\n".join(msgs)
		error_exit(final_msg)
	ok_exit()

def run():
	args = parse_arguments()
	folder = args['foldername']
	check_tf_file(folder)

run()
