
import networkx as nx 
from threading import RLock
class SyncronizedWeightedGraph() :
	def __init__(self) :
		self._lock = RLock()
		self._graph = nx.DiGraph()

	def add_arc(self, src, dst, port):
		self._lock.acquire()

		if (not self._graph.has_edge(src, dst)):
			self._graph.add_edge(src, dst, weight=0, port=port, time = 0, count = 0)
			
		self._lock.release()

	def update_weight(self, src, dst, curCount, curTime):
		self._lock.acquire()
		if (self._graph.has_edge(src, dst)):
			lastCount = self._graph[src][dst]['count']
			lastTime = self._graph[src][dst]['time']

			if (lastTime < curTime):
				self._graph[src][dst]['weight'] = (curCount - lastCount) / (curTime - lastTime)

				self._graph[src][dst]['count'] = curCount
				self._graph[src][dst]['time'] = curTime

				print(f'new weight is {self._graph[src][dst]["weight"]}@{src}->{dst}')
			else:
				print('Skipping negative-time update')
			
		else :
			print(f'Edge {src}->{dst} not found')
		self._lock.release()

	def get_shortest_path(self, src, dst):
		toReturn = []
		self._lock.acquire()
		toReturn = nx.shortest_path(
            self._graph,
            src,
            dst,
			weight="weight"
        )
		self._lock.release()
		return toReturn
	
	def path_to_hops(self, path):
		if (len(path) < 0):
			print('Path is empty!')
			return

		toReturn = {}
		self._lock.acquire()

		for i in range(len(path) - 1):
			src = path[i]
			dst = path[i + 1]
			toReturn[src] = self._graph[src][dst].copy()

		self._lock.release()
		return toReturn
