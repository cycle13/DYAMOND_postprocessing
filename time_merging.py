#!/usr/bin/env python
#SBATCH --job-name=model_mergetime
#SBATCH --output=logs/model_mergetime-%j.out

#SBATCH --account=um0878         # Charge resources on this project account
#SBATCH --partition=compute,compute2
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32       # Specify number of CPUs per task
#SBATCH --time=08:00:00          # Set a limit on the total run time
#SBATCH --mem=0                  # use all memory on node
#SBATCH --monitoring=meminfo=10,cpu=5,lustre=5
##SBATCH --mail-type=FAIL        # Notify user by email in case of job failure

import os
import numpy as np
from os.path import join
import processing_tools as ptools

config = ptools.config()
infiles, outfiles = ptools.get_mergingfilelist(**config)

ID = int(os.environ.get('SLURM_ARRAY_TASK_ID', 0)) # ID corresponds to variable

ptools.merge_timesteps(infiles[ID], outfiles[ID], **config)

