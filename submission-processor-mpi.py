import click
import pathlib
import os
import csv
from slurm import submit_slurm_job
from executor import run_command


#Changed to work with the makefile
executables = [{'compile_command': "make icccomplete", 'name': "stencil-complete-icc.exe", 'args' : ['{artifacts_path}/input_64_512_960.dat', '{artifacts_path}/kernel_5.dat', '{artifacts_path}/output_64_512_960x5.dat']}]

#Compiles based on the executable
def compile(basedir, artifacts_path):
    successful_compilations = []

    for exe in executables:
        command = exe['compile_command']
        e = exe["name"]
        command = command.format_map({'artifacts_path': artifacts_path})
        
	#Renamed to work with the makefile
        output_file_name = "stencil-complete-icc.exe"
        output_file_path = os.path.join(basedir, output_file_name)
        #Run_command located in executor
        p = run_command(command, cwd=basedir, output_file=output_file_path)

        rc = p.returncode
        print(rc)
        if rc == 0:
            path_to_executable = os.path.join(basedir, e)
            exe["full_path"] = path_to_executable
            successful_compilations.append(exe)
    
    return successful_compilations

#Sets up running the single instance runner. Indirectly linked to sine-instance-runner.py
def submit_job_for_run(exe, num_par, identifier, artifacts_path, basedir):
    args = [x.format_map({'artifacts_path': artifacts_path}) for x in exe["args"]]
    results_file_name = os.path.join(basedir, "iresults.csv")

    parValue = None
    resultsDone = False    
    print("num_par", num_par)
    try:
        with open(results_file_name, 'r') as file:
            results = csv.DictReader(file)
            for row in results:
                parValue = int(row['num_par'])
                exeName = row['executable']
                print("exe", exeName, "parValue", parValue)
                if exeName == exe["full_path"] and parValue == num_par:
                    resultsDone = True
    except FileNotFoundError:
        print("File does not exist")
    print(resultsDone)

    command_to_run = ["python", os.path.join(artifacts_path, "single-instance-runner.py")]
    command_to_run += ["--num-par", str(num_par)]
    command_to_run += ["--identifier", str(identifier)]
    command_to_run += ["--results-file", results_file_name]
    command_to_run += ["--basedir", basedir]
    command_to_run += ["--executable", exe["full_path"]]
    command_to_run += ["--args", ",".join(args)]
    command_to_run += ["--parallel", "MPI"]

    command_to_run = " ".join(command_to_run)
    cleanup_command = "rm %s" % args[-1]

    slurm_template = os.path.join(artifacts_path, "slurm_template.tpl")
    job_name = "%s_%s_%s" % (str(identifier), exe["name"], str(num_par))
    
    if resultsDone == False:
        return submit_slurm_job([command_to_run, cleanup_command], slurm_template, cwd=basedir,
                                time_limit=60, num_cores=1, num_tasks=num_par, job_name=job_name)

def submit_cleanup_job(basedir, identifier, artifacts_path, dependencies):
    command_to_run = ["python", os.path.join(artifacts_path, "cleanup-user.py")]
    command_to_run += ["--basedir", basedir]
    command_to_run += ["--identifier", str(identifier)]
    command_to_run += ["--leaderboard-path", artifacts_path]
    command_to_run += ["--iresults", "iresults.csv"]
    
    command_to_run = " ".join(command_to_run)
    slurm_template = os.path.join(artifacts_path, "slurm_template.tpl")
    job_name = "%s_cleanup" % str(identifier)
    return submit_slurm_job([command_to_run], slurm_template, cwd=basedir,
                            time_limit=60, num_cores=1, dependencies=dependencies,
                            job_name=job_name)


@click.command()
@click.option('--basedir', default=None, help='Directory to find executables')
@click.option('--identifier', required=True, help='Identify this submission')
@click.option('--artifacts-path', default=None, help='Location of artifacts')
def run(basedir, identifier, artifacts_path):
    if artifacts_path is None:
        artifacts_path = pathlib.Path(__file__).parent.resolve()
    
    basedir = os.path.abspath(basedir)
    
    executables = compile(basedir, artifacts_path)

    max_ranks = 33
    rank_nums = []
    ranknum = 1
    while ranknum < max_ranks:
        rank_nums.append(ranknum)
        ranknum *= 2
    rank_nums = list(reversed(rank_nums))

    job_ids = []
    for e in executables:
        for c in rank_nums:
            job_id = submit_job_for_run(e, c, identifier, artifacts_path, basedir)
            print(job_id)
            job_ids.append(job_id)
    print(job_ids)
    for j in job_ids:
    	if j != None:
            print(submit_cleanup_job(basedir, identifier, artifacts_path, job_ids))


if __name__=="__main__":
    run()
