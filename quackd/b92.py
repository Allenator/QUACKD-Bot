import random
import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning)

import numpy as np
from qiskit import Aer, execute, QuantumRegister, QuantumCircuit
from qiskit.ignis.mitigation.measurement import complete_meas_cal, CompleteMeasFitter

from globals import *


class B92:
    def __init__(
        self,
        alice_string,
        pbar,
        n=5,
        meas_err_mitig=False,
        n_shots=1024,
        backend=Aer.get_backend('aer_simulator'),
        **execute_kwargs
    ):
        self.pbar = pbar
        self._log_pbar('Started QKD protocol')

        # circuit
        self.alice_string = alice_string
        self.n = n
        self.bob_bases = np.random.choice(['X', 'Z'], len(self.alice_string))
        self.meas_err_mitig = meas_err_mitig
        self.n_shots = n_shots
        self.backend = backend
        self.execute_kwargs = execute_kwargs

        self.meas_fitters = [
            self.create_calibration_matrix(self.n, [i]) for i in range(self.n)
        ]

        self.basis_to_bit = {'Z': '1', 'X': '0'}

        self.inter_bit_string = ''
        self.known_indices = []

        # cascade
        self.N = -1
        self.Q = -1

        self.sent_digits = []
        self.corrected_digits = []

        self.parity_checks = [0]
        self.block_sizes = []

        self.errors = []

    def _log_pbar(self, msg):
        self.pbar.pos += 1
        self.pbar.log(msg)

    def create_calibration_matrix(self, qubits, qubit_list):
        """
        qubits [int]: number of qubits
        qubit_list [list] = list/array of qubits indexed into the backend
        """
        # create calibration circuits
        qr = QuantumRegister(qubits)
        meas_calibs, state_labels = complete_meas_cal(
            qubit_list=qubit_list, qr=qr, circlabel='cal'  # type: ignore
        )
        # create calibration matrix by running calibration
        job = execute(
            meas_calibs, backend=self.backend, shots=self.n_shots, **self.execute_kwargs
        )
        cal_results = job.result()  # type: ignore
        meas_fitter = CompleteMeasFitter(cal_results, state_labels, circlabel='cal')
        return meas_fitter

    def apply_measurement_error_mitigation(self, meas_fitter, raw_counts):
        """
        meas_fitter [qiskit ignis CompleteMeasFitter object]: calibration matrix fitter
        raw_counts [dict]: dictionary of bitstrings with respective counts
        """
        # apply measurement error mitigation via calibration matrix
        meas_filter = meas_fitter.filter
        mitigated_results = meas_filter.apply(raw_counts)
        return mitigated_results

    def build_circuit_n(self):
        if len(self.alice_string) != len(self.bob_bases):
            raise IndexError(
                'length of bit string and length of bases to measure in do not match'
            )
        else:
            length = len(self.alice_string)

        circuits = []

        for index in range(0, length, self.n):
            reg_len = self.n
            if length - index < self.n:
                reg_len = length - index

            qr = QuantumRegister(reg_len)
            circuit = QuantumCircuit(qr)
            bits = self.alice_string[index : index + reg_len]
            bases = self.bob_bases[index : index + reg_len]

            # Step 1: Initialize qubits according to Alice's bit string
            for r in range(reg_len):
                bit = bits[r]

                if bit == '0':  # if the bit is 0
                    circuit.i(qr[r])  # we initialize the qubit in the |0> state
                elif bit == '1':  # if the bit is 1
                    circuit.h(qr[r])  # we initialize the qubit in the |+> state

            # Step 2: Measure qubits in Bob's chosen bases
            for r in range(reg_len):
                basis = bases[r]

                if basis.upper() == 'Z':  # if Bob picks the Z basis,
                    circuit.i(qr[r])  # we stay in the Z basis
                elif basis.upper() == 'X':  # if Bob picks the X basis,
                    # we apply a Hadamard gate so that the measurement will be in the Z basis
                    circuit.h(qr[r])

            circuit.measure_all()
            circuits.append(circuit)

        self._log_pbar('Synthesized B92 circuits')
        # Step 3: run the circuits on the Quantum Inspire backend and compile the results
        qi_job = execute(circuits, backend=self.backend, shots=self.n_shots)
        self._log_pbar('Submitted jobs to backend')
        qi_result = qi_job.result()  # type: ignore
        self._log_pbar('Acquired measurement results')

        # Step 4: collect bits based on measurement results
        for index in range(0, length, self.n):
            reg_len = self.n
            if length - index < self.n:
                reg_len = length - index

            bases = self.bob_bases[index : index + reg_len]
            bits = self.alice_string[index : index + reg_len]
            circuit = circuits[index // self.n]
            histogram = qi_result.get_counts(circuit)

            for r in range(reg_len):

                eigvl_cnts = {'0': 0, '1': 0}

                for key in histogram:
                    eigvl_cnts[key[reg_len - 1 - r]] += histogram[key]

                if self.meas_err_mitig:
                    eigvl_cnts = self.apply_measurement_error_mitigation(
                        self.meas_fitters[r], eigvl_cnts
                    )

                if '0' not in eigvl_cnts:
                    eigvl_cnts['0'] = 0  # type: ignore
                if '1' not in eigvl_cnts:
                    eigvl_cnts['1'] = 0  # type: ignore

                if eigvl_cnts['1'] >= 0.3 * self.n_shots:  # type: ignore
                    basis = bases[r]
                    bit = self.basis_to_bit[basis.upper()]
                    # this index with eigvl = -1 gives a determined bit that we append to known_indices
                    self.known_indices.append(index + r)
                else:
                    bit = 'n'  # bit is indeterminate

                self.inter_bit_string += bit

        self._log_pbar('Sifted keys from matching bases')
        # initialize for cascade
        self.sent_digits = [self.alice_string[index] for index in self.known_indices]
        self.corrected_digits = [
            self.inter_bit_string[index] for index in self.known_indices
        ]
        self.N = len(self.known_indices)
        self.Q = np.mean(np.array(self.sent_digits) != np.array(self.corrected_digits))

    # count parity
    def parity(self, block):
        return block.count('1') % 2

    # binary split and correct odd parities
    def bin_split(self, si, fi, parity_cnt=1):
        if fi < self.N:
            block_a = self.sent_digits[si:fi]
            block_b = self.corrected_digits[si:fi]
        else:
            block_a = self.sent_digits[si : self.N - 1] + [self.sent_digits[self.N - 1]]
            block_b = self.corrected_digits[si : self.N - 1] + [
                self.corrected_digits[self.N - 1]
            ]

        if self.parity(block_a) != self.parity(block_b):
            if fi - si == 1:
                # '0' -> '1' and '1' -> '0'
                self.corrected_digits[si] = str(1 - int(self.corrected_digits[si]))
                return parity_cnt
            else:
                # right block bigger
                mid = si + (fi - si) // 2
                return self.bin_split(si, mid, parity_cnt + 1) + self.bin_split(
                    mid, fi, parity_cnt + 1
                )
        else:
            return 1

    def getperm(self, iter_n, block):
        random.seed(iter_n)
        perm = list(range(len(block)))
        random.shuffle(perm)
        random.seed()  # optional, in order to not impact other code based on random
        return perm

    def shuffle(self, iter_n, block):
        perm = self.getperm(iter_n, block)
        block[:] = [block[j] for j in perm]

    def unshuffle(self, iter_n, block):
        perm = self.getperm(iter_n, block)
        res = [None] * len(block)
        for i, j in enumerate(perm):
            res[j] = block[i]
        block[:] = res

    # shuffle, binary split blocks, unshuffle
    def cascade(self, iter_n):

        if self.Q == 0.0:
            k = self.N
        else:
            k = min(int(0.73 / self.Q * 2 ** iter_n), self.N)
        self.block_sizes.append(k)

        self.shuffle(iter_n, self.sent_digits)
        self.shuffle(iter_n, self.corrected_digits)

        # binary split blocks and count parity checks
        iter_n_parity_checks = 0
        for i in range(0, self.N, k):
            if i + k <= self.N:
                iter_n_parity_checks += self.bin_split(i, i + k)
            else:
                iter_n_parity_checks += self.bin_split(i, self.N)

        self.parity_checks.append(self.parity_checks[-1] + iter_n_parity_checks)

        self.unshuffle(iter_n, self.sent_digits)
        self.unshuffle(iter_n, self.corrected_digits)

    def correct_bobs_digits(self, num_cascade_iters=5):
        self.errors = [self.Q]
        for c in range(num_cascade_iters):
            self.cascade(c)
            error = np.mean(
                np.array(self.sent_digits) != np.array(self.corrected_digits)
            )
            self.errors.append(error)
        self._log_pbar('Completed cascade information reconciliation')

    def generate_corrected_key(self):
        self.build_circuit_n()
        self.correct_bobs_digits()
        return ''.join(self.corrected_digits)

    def get_key_pair(self):
        corrected_digits = self.generate_corrected_key()
        self._log_pbar('Finished QKD protocol')
        return ''.join(self.sent_digits), corrected_digits
