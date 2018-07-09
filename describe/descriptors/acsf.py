from __future__ import absolute_import, division, print_function, unicode_literals
from builtins import (bytes, str, open, super, range, zip, round, input, int, pow, object)

import numpy as np
from ctypes import cdll, Structure, c_int, c_double, POINTER, byref

from describe.descriptors.descriptor import Descriptor


libacsf = cdll.LoadLibrary("../libacsf/libacsf.so")


class ACSFObject(Structure):
	_fields_ = [
		('natm', c_int),
		('Z', POINTER(c_int)),
		('positions', POINTER(c_double)),
		('nTypes', c_int),
		('types', POINTER(c_int)),
		('typeID', (c_int*100)),
		('nSymTypes', c_int),
		('cutoff', c_double),

		('n_bond_params', c_int),
		('bond_params', POINTER(c_double)),

		('n_bond_cos_params', c_int),
		('bond_cos_params', POINTER(c_double)),

		('n_ang_params', c_int),
		('ang_params', POINTER(c_double)),


		('distances', POINTER(c_double)),
		('nG2', c_int),
		('nG3', c_int),
		('G2', POINTER(c_double)),
		('G3', POINTER(c_double)),

		('acsfs', POINTER(c_double)),

		('alloc_atoms', c_int),
		('alloc_work', c_int)
	]
 
# libacsf.acsf_init.argtypes = [POINTER(ACSFObject)]
# libacsf.acsf_reset.argtypes = [POINTER(ACSFObject)]
libacsf.acsf_compute_acsfs.argtypes = [POINTER(ACSFObject)]



class ACSF(Descriptor):
	
	
	
	def __init__(self, n_atoms_max, types, bond_params=None, bond_cos_params=None, ang_params=None, flatten=True):

		"""
		Args:
		flatten (bool): Whether the output of create() should be flattened
		to a 1D array.
		"""
		super().__init__(flatten)
		self._inited = False

		self._obj = ACSFObject()
		self._obj.alloc_atoms = 0
		self._obj.alloc_work  = 0

		#print(self._obj.alloc_work)

		'''// number of 2- and 3-body ACSFs per atom!
		//qm->nG2 = 1 + NBONDETA*NBONDRS + NBONDCOS;
		//qm->nG3 = 2*NBONDETA*NANGZETA;
		//qm->nG3 = 4*NBONDETA*NANGZETA; // for the Gang45 version
		'''
		if n_atoms_max <= 0:
			raise ValueError("Maximum number of atoms n_atoms_max should be positive.")
			
		self._n_atoms_max = n_atoms_max

		self._types = None
		self.types = types

		self._Zs = None

		self._bond_params = None
		self.bond_params = bond_params # np.array([[5.0, 0.0],[1.0, 0.0],[0.5, 0.0],[0.1, 0.0]])

		self._bond_cos_params = None
		self.bond_cos_params = bond_cos_params


		self._ang_params = None
		self.ang_params = ang_params # np.array([[0.1, 1, 1],[0.1, 1, -1],[0.1, 2, 1],[0.1, 2, -1]])


		self._rcut = None
		self.rcut = 5.0

		self.positions = None
		self.distances = None


		self._acsfBuffer = None

		self.acsf_bond = None
		self.acsf_ang = None

		self._inited = True


	# --- TYPES ---
	@property
	def types(self):
		return self._types


	@types.setter
	def types(self, value):

		if self._inited:
			raise ValueError("Cannot change the atomic types.")

		if value == None:
			raise ValueError("Atomic types cannot be None.")


		pmatrix = np.array(value, dtype=np.int32)

		if pmatrix.ndim != 1:
			raise ValueError("Atomic types should be a vector of integers.")

		pmatrix = np.unique(pmatrix)
		pmatrix = np.sort(pmatrix)

		print("Setting types to: "+str(pmatrix))

		self._types = pmatrix
		self._obj.types = pmatrix.ctypes.data_as(POINTER(c_int))

		# set the internal indexer
		self._obj.nTypes = c_int(pmatrix.shape[0])
		self._obj.nSymTypes = c_int(int((pmatrix.shape[0]*(pmatrix.shape[0]+1))/2))

		for i in range(pmatrix.shape[0]):
			self._obj.typeID[ self._types[i] ] = i

	# --- ----- ---




	# --- CUTOFF RADIUS ---
	@property
	def rcut(self):
		return self._rcut

	@rcut.setter
	def rcut(self,value):

		self._rcut = c_double(value)
		self._obj.cutoff = c_double(value)

	# --- ------------- ---


	# --- BOND PARAMETERS ---

   	@property
	def bond_params(self):
		return self._bond_params
 
	@bond_params.setter
	def bond_params(self,value):

		# TODO: check that the user input makes sense...
		# ...
		if self._inited:
			raise ValueError("Cannot change 2-body ACSF parameters.")

		# handle the disable case
		if value == None: 
			# print("Disabling 2-body ACSFs...")
			self._obj.n_bond_params = 0
			self._bond_params = None
			return


		pmatrix = np.array(value, dtype=np.double) # convert to array just to be safe!
		print("Setting 2-body ACSFs...")


		if pmatrix.ndim != 2:
			raise ValueError("arghhh! bond_params should be a matrix with two columns (eta, Rs).")

		if pmatrix.shape[1] != 2:
			raise ValueError("arghhh! bond_params should be a matrix with two columns (eta, Rs).")

		# store what the user gave in the private variable
		self._bond_params = pmatrix


		# get the number of parameter pairs
		self._obj.n_bond_params = c_int(pmatrix.shape[0])

		# convert the input list to ctypes
		#self._obj.bond_params = c_double(pmatrix.shape[0] * pmatrix.shape[1])

		#assign it
		self._obj.bond_params = self._bond_params.ctypes.data_as(POINTER(c_double))
	
	# --- --------------- ---

	# --- COS PARAMS ---

   	@property
	def bond_cos_params(self):
		return self._bond_cos_params
 
	@bond_cos_params.setter
	def bond_cos_params(self,value):

		# TODO: check that the user input makes sense...
		# ...
		if self._inited:
			raise ValueError("Cannot change 2-body Cos-type ACSF parameters.")

		# handle the disable case
		if value == None: 
			print("Disabling 2-body COS-type ACSFs...")
			self._obj.n_bond_cos_params = 0
			self._bond_cos_params = None
			return



		pmatrix = np.array(value, dtype=np.double) # convert to array just to be safe!
		print("Setting 2-body COS-type ACSFs...")

		if pmatrix.ndim != 1:
			raise ValueError("arghhh! bond_cos_params should be a vector.")

		# store what the user gave in the private variable
		self._bond_cos_params = pmatrix


		# get the number of parameter pairs
		self._obj.n_bond_cos_params = c_int(pmatrix.shape[0])

		#assign it
		self._obj.bond_cos_params = self._bond_cos_params.ctypes.data_as(POINTER(c_double))


	# --- ---------- ---


	# --- ANG PARAMS ---

	@property
	def ang_params(self):
		return self._ang_params
 
	@ang_params.setter
	def ang_params(self,value):

		# TODO: check that the user input makes sense...
		# ...
		if self._inited:
			raise ValueError("Cannot change 3-body ACSF parameters.")

		# handle the disable case
		if value == None: 
			print("Disabling 3-body ACSFs...")
			self._obj.n_ang_params = 0
			self._ang_params = None
			return

		pmatrix = np.array(value, dtype=np.double) # convert to array just to be safe!
		print("Setting 3-body ACSFs...")

		if pmatrix.ndim != 2:
			raise ValueError("arghhh! ang_params should be a matrix with three columns (eta, zeta, lambda).")
		if pmatrix.shape[1] != 3:
			raise ValueError("arghhh! ang_params should be a matrix with three columns (eta, zeta, lambda).")

		# store what the user gave in the private variable
		self._ang_params = pmatrix


		# get the number of parameter pairs
		self._obj.n_ang_params = c_int(pmatrix.shape[0])

		#assign it
		self._obj.ang_params = self._ang_params.ctypes.data_as(POINTER(c_double))
	
	# --- ---------- ---




	def Compute(self):

		lib.acsf_reset(byref(self._obj))

		self._obj.nG2 = c_int(1 + self._obj.neta * self._obj.nrs + self._obj.ncos);
		self._obj.nG3 = c_int(2 * self._obj.neta * self._obj.nzeta);

		lib.acsf_init(byref(self.obj))
		lib.acsf_compute_acsfs(byref(self.obj))

		self.acsf_bond = numpy.ctypeslib.as_array(self.obj.G2, 
		shape=(self.obj.natm, self.obj.nTypes, self.obj.nG2))

		self.acsf_ang = numpy.ctypeslib.as_array(self.obj.G3, 
		shape=(self.obj.natm, self.obj.nSymTypes, self.obj.nG3))
	

	def describe(self, system):
		"""Creates the descriptor for the given systems.

		Args:
		system (System): The system for which to create the
		descriptor.

		Returns:
		A descriptor for the system in some numerical form.
		"""

		if self._types == None:
			# GIVE AN ERROR
			raise ValueError("No atomic types declared for the descriptor.")


		# copy the atomic numbers
		self._Zs = np.array(system.get_atomic_numbers(), dtype=np.int32)

		if self._Zs.shape[0] > self._n_atoms_max:
			raise ValueError("The system has more atoms than n_atoms_max.")


		self._obj.Z = self._Zs.ctypes.data_as(POINTER(c_int))
		self._obj.natm = c_int(self._Zs.shape[0])

		# check the types in the system
		typs = np.array(system.get_atomic_numbers())
		typs = np.unique(typs)
		typs = np.sort(typs)


		# check if there are types not declared in self.types
		isin = np.in1d(typs, self._types)
		isin = np.unique(isin)

		if isin.shape[0] > 1 or isin[0] == False:
			raise ValueError("The system has types that were not declared.")


		self.positions = np.array(system.get_positions(), dtype=np.double)
		self._obj.positions = self.positions.ctypes.data_as(POINTER(c_double))

		self.distances = system.get_distance_matrix()
		self._obj.distances = self.distances.ctypes.data_as(POINTER(c_double))


		# amount of ACSFs for one atom for each type pair or triplet
		self._obj.nG2 = c_int(1 + self._obj.n_bond_params + self._obj.n_bond_cos_params);
		self._obj.nG3 = c_int(self._obj.n_ang_params);


		self._acsfBuffer = np.zeros((self._n_atoms_max, self._obj.nG2 * self._obj.nTypes + self._obj.nG3 * self._obj.nSymTypes))
		self._obj.acsfs = self._acsfBuffer.ctypes.data_as(POINTER(c_double))


		libacsf.acsf_compute_acsfs(byref(self._obj))

		if self.flatten == True:
			return self._acsfBuffer.flatten()
		
		return self._acsfBuffer


	def get_number_of_features(self):
		"""Used to inquire the final number of features that this descriptor
		will have.

		Returns:
		int: Number of features for this descriptor.
		"""
	
		descsize = (1 + self._obj.n_bond_params + self._obj.n_bond_cos_params) * self._obj.nTypes
		descsize += self._obj.n_ang_params * self._obj.nSymTypes

		descsize *= self._n_atoms_max

		return descsize




