#!/bin/bash
#SBATCH --job-name=3DFFish

#SBATCH --time=72:00:00   # Use the form DD-HH:MM:SS
#SBATCH --ntasks=3
#SBATCH --ntasks-per-node=3
#SBATCH --nodes=1
#SBATCH --cpus-per-task=6
#SBATCH --output=out
#SBATCH --partition=standard
#SBATCH --constraint=afton
#SBATCH -A FSRG

#SBATCH --mail-user=trh6km@virginia.edu
#SBATCH --mail-type=ALL   # same as =BEGIN,FAIL,END

module load intel/2023.1

ulimit -s unlimited
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK


srun  ./picar3d-2.9.2-FSI
