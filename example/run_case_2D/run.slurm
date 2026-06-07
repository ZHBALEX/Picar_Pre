#!/bin/bash
#SBATCH --job-name=FfoilP

#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=7-00:00:00
#SBATCH --output=out
#SBATCH --partition=standard
#SBATCH -A fsrg
#SBATCH --mail-user=trh6km@virginia.edu
#SBATCH --mail-type=ALL

module load intel
ulimit -s unlimited
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
export LD_LIBRARY_PATH=/home/jk3vz/opt/lib/:$LD_LIBRARY_PATH
export OMP_PLACES=CORES

srun   ./picar3d-2.9.1_UndCont
