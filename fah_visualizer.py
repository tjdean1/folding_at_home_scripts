'''
This script is based off of the original tutorial at
msmbuilder.org/3.8.0/tutorial.html
and developed by mpharrigan
'''

# Add necessary packages
import os
import mdtraj as md
from msmbuilder.featurizer import DihedralFeaturizer
from msmbuilder.decomposition import tICA
from msmbuilder.io.sampling import sample_dimension
from msmbuilder.io import gather_metadata, save_meta, NumberedRunsParser, load_meta,\
    preload_top, preload_tops, save_trajs, save_generic, backup, load_trajs
from multiprocessing import Pool

# STEP 0.5 META pickle file of trajectories
atom_index_start, atom_index_end, number_between =\
    [int(x) for x in input("What is the start, end, and jump between atom index numbers: ").split()]
traj_name = input("Name of the trajectory files: ")  # Note need to be in 'trajectory-{run}.xtc' format for function
top_name = input("Name of the topology file for the system: ")  # Just need to give the name of file ex. 'top.pdb'
frame_step = int(input("What is the trajectory frame step in picoseconds: "))  # Need to be in ps for it to work
frame_num_desired = int(input("How many frames would you like in the output trajectory: "))
output_trajectory = input("What would you like to name your output trajectory: ")
parser = NumberedRunsParser(traj_name, top_name, frame_step)

meta = gather_metadata(os.getcwd() + "/*.xtc", parser)
save_meta(meta)

# STEP 1 Run Featurization of trajectories
metadata = load_meta()
tops = preload_tops(metadata)
dihed_feat = DihedralFeaturizer()  # Currently only uses dihedral features, can update with additional options

def feat(irow):
    i, row = irow
    traj = md.load(row['traj_fn'], top=tops[row['top_fn']])
    feat_traj = dihed_feat.partial_transform(traj)
    return i, feat_traj


with Pool() as pool:
    dihed_trajs = dict(pool.imap_unordered(feat, meta.iterrows()))

save_trajs(dihed_trajs, 'ftrajs', metadata)
save_generic(dihed_feat, 'featurizer.pickl')

# Step 2 Run tICA on feature space and compute tICA components
tica = tICA(n_components=5, lag_time=100, kinetic_mapping=True)
meta_info, ftrajs = load_trajs("ftrajs")

tica.fit(ftrajs.values())

ttrajs = {}
for k, v in ftrajs.items():
    ttrajs[k] = tica.partial_transform(v)

save_trajs(ttrajs, 'ttrajs', meta_info)
save_generic(tica, 'tica.pickl')

# Step 3-4, Cluster with tICA, set the spline of tIC0, and extract those states to a trajectory
meta_step3, ttrajs_step3 = load_trajs('ttrajs')

inds = sample_dimension(ttrajs_step3,
                        dimension=0,
                        n_frames=frame_num_desired, scheme='random')

save_generic(inds, "tica-dimension-0-inds.pickl")

top = preload_top(meta_step3)

traj = md.join(
    md.load_frame(meta_step3.loc[traj_i]['traj_fn'], index=frame_i, top=top)
    for traj_i, frame_i in inds
)

# Step 5, extract states as a signle trajectory and align them
ref_file = md.load(top_name)
traj.superpose(ref_file)
traj_fn = output_trajectory
backup(traj_fn)
traj.save(traj_fn)
