import argparse
import os
import pdb
import shutil
import sys
import intermol.unit as units
import subprocess

#--------DESMOND energy evaluation methods---------#
def parse_args():
    parser = argparse.ArgumentParser(description = 'Evaluate energy of file')
    group_in = parser.add_argument_group('Choose input format')
    group_in.add_argument('--des_in', nargs=1, metavar='file', help='.cms file for conversion from DESMOND file format')
    group_in.add_argument('--gro_in', nargs=2, metavar='file', help='.gro and .top file for conversion from GROMACS file format')
    group_in.add_argument('--lmp_in', nargs=1, metavar='file', help='.lmp file for conversion from LAMMPS file format')

    group_misc = parser.add_argument_group('Other optional arguments')
    group_misc.add_argument('--cfg', default='Inputs/Desmond/onepoint.cfg', help="input .cfg file (for DESMOND)")
    group_misc.add_argument('--mdp', default='Inputs/Gromacs/grompp.mdp', help="input .mdp file (for GROMACS)")
    group_misc.add_argument('-d', '--despath', dest='despath', metavar='path', default='', help='path for DESMOND binary, needed for energy evaluation')
    group_misc.add_argument('-g', '--gropath', dest='gropath', metavar='path', default='', help='path for GROMACS binary, needed for energy evaluation')
    group_misc.add_argument('-l', '--lmppath', dest='lmppath', metavar='path', default='', help='path for LAMMPS binary, needed for energy evaluation')
    # to do: add arguments for other file types
    args = parser.parse_args()
    return args

def get_desmond_energy_from_file(energy_file):
    ''' 
    parses the desmond energy file
    for now, returns just the total energy
    '''
    with open(energy_file, 'r') as f:
        for line in f:
            if 'Total' in line:
                tot_energy = line.split()[-1]
                break
    return tot_energy

def get_gromacs_energy_from_file(energy_file):
    # extract g_energy output and parse initial energies
    with open(energy_file) as f:
        all_lines = f.readlines()

    # take last line
    sec_last = all_lines[-1].split()[1:]
    data = map(float, sec_last)

    # give everything units
    temp = data[-1] * units.kelvin
    data = [value * units.kilojoules_per_mole for value in data[:-1]]
    data.append(temp)

    # pack it all up in a dictionary
    types = ['Bond', 'Angle', 'Proper Dih.', 'Ryckaert-Bell.', 'LJ-14', 'Coulomb-14',
            'LJ (SR)', 'Disper. corr.', 'Coulomb (SR)', 'Coul. recip.', 'Potential',
            'Kinetic En.', 'Total Energy', 'Temperature']
    e_out = dict(zip(types, data))
    return e_out
 
def desmond_energies(cms, cfg, despath):
    """
    Evalutes energies of DESMOND files
    Args:
        cms = cms file
        cfg = cfg file
        despath = path to DESMOND binaries

    """
    cms = os.path.abspath(cms)
    cfg = os.path.abspath(cfg)
    direc, cms_filename = os.path.split(cms)
    cwd = os.getcwd()
    name = 'system'
    energy_file = '%s/%s.enegrp.dat' % (direc, name)
    desmond_bin = os.path.join(despath,'desmond')

    # first see if the file already exists
    if os.path.exists(energy_file):
        print '%s already exists, not running DESMOND' % energy_file
        tot_energy = get_desmond_energy_from_file(energy_file)
        return tot_energy, energy_file

    # use DESMOND To evaluate energy
    #    cd to directory of cms file so that files generated by desmond
    #    don't clog the working directory
    os.chdir(direc)   
    if os.path.exists('trj'):
        shutil.rmtree('trj')
    cmd = '{desmond_bin} -WAIT -P 1 -in {cms} -JOBNAME {name} -c {cfg}'.format(desmond_bin=desmond_bin, name=name, cms=cms, cfg=cfg)
    print 'Running DESMOND with command'
    print cmd
    exit = os.system(cmd)
    if exit: # exit status not 0
        print 'Failed evaluating energy of {0}'.format(cms)
        os.chdir(cwd)
        sys.exit(1)
    
    # parse desmond energy file
    os.chdir(cwd)
    tot_energy = get_desmond_energy_from_file(energy_file)
    return tot_energy, energy_file

#--------GROMACS energy evaluation methods---------#
# to do: clean up

def gromacs_energies(top, gro, mdp, gropath, grosuff):
    """

    gropath = path to gromacs binaries
    grosuff = suffix of gromacs binaries, usually '' or '_d'

    """
    direc, _  =  os.path.split(top) # intermediate and energy files will be in the same directory as .top file

    tpr = os.path.join(direc, 'topol.tpr')
    ener = os.path.join(direc, 'ener.edr')
    ener_xvg = os.path.join(direc, 'energy.xvg')
    conf = os.path.join(direc, 'confout.gro')
    mdout = os.path.join(direc, 'mdout.mdp')
    state = os.path.join(direc, 'state.cpt')
    traj = os.path.join(direc, 'traj.trr')
    log = os.path.join(direc, 'md.log')

    grompp_bin = os.path.join(gropath, 'grompp' + grosuff)
    mdrun_bin = os.path.join(gropath, 'mdrun' + grosuff)
    genergy_bin = os.path.join(gropath, 'g_energy' + grosuff)

    # grompp'n it up
    cmd = "{grompp_bin} -f {mdp} -c {gro} -p {top} -o {tpr} -po {mdout} -maxwarn 1".format(grompp_bin=grompp_bin,
            mdp=mdp, top=top, gro=gro, tpr=tpr, mdout=mdout)
    print 'Running GROMACS with command'
    print cmd
    exit = os.system(cmd)
    if exit:
        print 'Failed at evaluating energy of {0}'.format(top)
        sys.exit(1)


    # mdrunin'
    cmd = "{mdrun_bin} -s {tpr} -o {traj} -cpo {state} -c {conf} -e {ener} -g {log}".format(mdrun_bin=mdrun_bin,
            tpr=tpr, traj=traj, state=state, conf=conf, ener=ener, log=log)
    print cmd
    exit = os.system(cmd)
    if exit:
        print 'Failed at evaluating energy of {0}'.format(top)
        sys.exit(1)

    # energizin'
    select = " ".join(map(str, range(1, 15))) + " 0 "
    cmd = "echo {select} | {genergy_bin} -f {ener} -o {ener_xvg} -dp".format(select=select, genergy_bin=genergy_bin,
            ener=ener,ener_xvg=ener_xvg)
    print cmd
    exit = os.system(cmd)
    if exit:
        print 'Failed at evaluating energy of {0}'.format(top)
        sys.exit(1)

    e_out = get_gromacs_energy_from_file(ener_xvg)
    return e_out, ener_xvg

#--------LAMMPS energy evaluation methods---------#
#to do: clean up

def lammps_energies(name, in_out='in', lmppath='', lmpbin='lmp_openmpi',
        verbose=False):
    """Evaluate energies of LAMMPS files

    Args:
        lmppath = path to LAMMPS binaries
        lmpbin = name of LAMMPS binary
    """

    if in_out == 'in':
        base = 'Inputs/Lammps'
    elif in_out == 'GtoL':
        base = 'Outputs/GromacsToLammps'
    elif in_out == 'LtoL':
        base = 'Outputs/LammpsToLammps'
    else:
        raise Exception("Unknown flag: {0}".format(in_out))

    lmpbin = os.path.join(lmppath, lmpbin)
    sim_dir = os.path.join(base, name)
    log = os.path.join(sim_dir, 'log.lammps')

    # mdrunin'
    saved_path = os.getcwd()
    os.chdir(sim_dir)
    if verbose:
        run_lammps = "{lmpbin} < data.input".format(lmpbin=lmpbin)
    else:
        run_lammps = "{lmpbin} < data.input > /dev/null".format(lmpbin=lmpbin)
    #run_lammps = "{lmpbin} < input_file.out".format(lmpbin=lmpbin)
    os.system(run_lammps)
    os.chdir(saved_path)

    # energizin'
    proc = subprocess.Popen(["awk '/E_bond/{getline; print}' %s" % (log)],
            stdout=subprocess.PIPE, shell=True)
    (energies, err) = proc.communicate()

    data = map(float, energies.split())

    # give everything units
    #temp = data[-1] * units.kelvin
    data = [value * units.kilocalories_per_mole for value in data]
    #data.append(temp)

    # pack it all up in a dictionary
    types = ['Bond', 'Angle', 'Proper Dih.', 'Improper', 'Pairs', 'vdW', 'Coulomb', 'Potential']

    e_out = dict(zip(types, data))
    return e_out

def main():
    args = parse_args()
    if args.des_in:
        energy, energy_file = desmond_energies(args.des_in[0], args.cfg, args.despath)
        print 'Total energy from %s:' % energy_file
        print energy
    elif args.gro_in:
        top = [x for x in args.gro_in if x.endswith('.top')] # filter out the top
        gro = [x for x in args.gro_in if x.endswith('.gro')] # filter out the gro
        e_out, energy_file = gromacs_energies(top[0], gro[0], args.mdp, args.gropath, '')
        print 'Energy from %s:' % energy_file
        print e_out
    elif args.lmp_in:
        pass
    else:
        print 'no file given'
    
if __name__ == '__main__':
    main()
