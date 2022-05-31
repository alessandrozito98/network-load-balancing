
from threading import RLock
class SyncronizedDict() :
	def __init__(self) :
		self._lock = RLock()
		self._dict = {}
	# Return Tuple
	# Ok: True if found (data is valid), false if not found (data MUST be discarded)
	# Data: The saved dict, returned as a shallow copy

	# DatapathId: Id of the datapath the host is connected to
	# PortID: Id of the port (on the datapath) the host is connected to
	def get(self, key, display = False):

		toReturn = (False, ())
		self._lock.acquire()

		if (key in self._dict):
			toReturn = (True, self._dict[key].copy())

		self._lock.release()
		return toReturn

	def set(self, key, **data):

		self._lock.acquire()

		self._dict[key] = data.copy()

		self._lock.release()

	def list(self):
		toReturn = []
		self._lock.acquire()

		for key in self._dict:
			valid, data = self.get(key)
			if (valid):
				toReturn.append((key, data))
				
		self._lock.release()

		return toReturn
