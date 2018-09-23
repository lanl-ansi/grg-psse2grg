import os, warnings

warnings.simplefilter('always')


idempotent_files = []

for wd, directory, files in os.walk(os.path.dirname(os.path.realpath(__file__))+'/data/idempotent'):
    for file in files:
        if file.endswith('.raw'):
            idempotent_files.append(wd+'/'+file)
#del wd, directory, files


correct_files = []

for wd, directory, files in os.walk(os.path.dirname(os.path.realpath(__file__))+'/data/correct'):
    for file in files:
        if file.endswith('.raw'):
            correct_files.append(wd+'/'+file)
del wd, directory, files


warning_files = []

for wd, directory, files in os.walk(os.path.dirname(os.path.realpath(__file__))+'/data/warning'):
    for file in files:
        if file.endswith('.raw'):
            warning_files.append(wd+'/'+file)
#del wd, directory, files


incorrect_files = []

for wd, directory, files in os.walk(os.path.dirname(os.path.realpath(__file__))+'/data/exception'):
    for file in files:
        if file.endswith('.raw'):
            incorrect_files.append(wd+'/'+file)
del wd, directory, files
