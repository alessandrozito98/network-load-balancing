#  cd sdn-project/ && gh repo sync && cd .. && ryu-manager sdn-project/controller.py flowmanager/flowmanager.py
# Assuming topology discovery (ryu-manager --observe-links)
# Assuming switch topology doesn't change over time

# Table 0 is for rejecting multicast traffic from neighbor switches
# Table - is for handling ARP (and similar) traffic
# - ARP requests are handled by the controller
# - Non-IP packets are discarded (?)
# - Remaining traffic is directed to the next table

# Table 1 is for handling defined routes
# - Each time a new connection is detected the specific route for that is computed by the controller and pushed in this table
# - Unmatched packets will be directed to the controller

# - ARP Traffic is handled by the controller
# - IPv6 Traffic is discarded switch-level
# - IPv4 TCP traffic is load balanced through the network
# - Remaining Ethernet traffic is delivered through the controller directly to the destination switch
# - Unmatched traffic is discarded controller-level

# IPv6 Traffic is discarded
# TCP Connections are load balanced through the network
# Ethernet Multicast from a switch is discarded switch level (rules are created when a switch is registered)
# Ethernet Multicast is delivered to the controller to be broadcasted to all switches
# Remaining traffic is logged and discarded

# ---
# Assuming topology discovery (ryu-manager --observe-links)

# Table 0 is system-reserved (eg topology discovery)
# Table 1 is for dropping multicast traffic originated from a controlled switch. Rules are added dynamically.
# Table 2 is for handling TCP connections. Unmatched traffic is directed to the controller
 
# Due to a bug on tcp_src transformed in tp_src and tcp_dst transformed in udp_dst (present in hubrewrite1, too) we removed connection discrimination via port
from tkinter.messagebox import NO
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3, inet
from ryu.lib.packet import packet, ethernet, arp, lldp, ipv4, ipv6, tcp, ether_types
from ryu.lib import hub, mac
from ryu.topology import event, switches
from ryu.topology.api import get_all_switch, get_all_link, get_all_host
import networkx as nx 

from threading import Lock
from SyncronizedDict import SyncronizedDict
from SyncronizedWeightedGraph import SyncronizedWeightedGraph 
class WeightedLoadBalancer(app_manager.RyuApp):
	OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
	BGWORKER_THREAD_INTERVAL = 15

	def __init__(self, *args, **kwargs):
		super(WeightedLoadBalancer, self).__init__(*args, **kwargs)

		# Weighted network map
		# self.net = nx.DiGraph()

		# self.net_mutex = Lock()
		self.host_dp_assoc = SyncronizedDict()
		self.datapaths = SyncronizedDict()
		self.portstats = SyncronizedDict()

		self.graph = SyncronizedWeightedGraph()
		
		# thread che lancia periodicamente le richieste
		# self.monitor_thread = hub.spawn(self._monitor_thread_f)
		self.net_mapper_thread = hub.spawn(self._bgworker_thread_f)
		self.connections = SyncronizedDict()
	def dump(self, obj):
		attrs = vars(obj)
		print(f', '.join("%s: %s\n" % item for item in attrs.items()))

	# def _monitor_thread_f(self):
	# 	while True:
	# 		print('\nAsking stats:')
	# 		for dpid, _ in self.datapaths.list():
	# 			ok, datapath,ofproto,parser = self.get_datapath(dpid)
	# 			if ok:
	# 				# req = parser.OFPFlowStatsRequest(datapath)
	# 				# datapath.send_msg(req)
	# 				req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
	# 				datapath.send_msg(req)
	# 		hub.sleep(self.STATS_THREAD_INTERVAL)

	# def net_update_weight(self, datapath, port, updateId, totalLoad):




	# 	# Computing src and desc id
	# 	src = datapath.id
	# 	dst = self.datapaths[src][port]
	# 	assert dst != None

	# 	self.net_mutex.acquire()
	# 	link = self.net[src][dst]
	# 	assert link != None

	# 	interval = updateId - link.updateId
	# 	if (interval < 0):
	# 		return  #Old Update
		
	# 	link.weight = totalLoad - link.totalLoad
	# 	link.totalLoad = totalLoad
	# 	self.net_mutex.release()

	def add_datapath(self, dp):
		(ok, _) = self.datapaths.get(dp.id)
		if (not ok):
			self.datapaths.set(dp.id, ref=dp)
			self._bgworker_f()
			print(f'Discovered new datapath {dp.id}')

	def add_node(self, mac, dpid, port):
		(ok, _)  =self.host_dp_assoc.get(mac)
		if (not ok):
			self.host_dp_assoc.set(mac, dpid= dpid, port= port)
			self._bgworker_f()
			print(f'Discovered new Node {mac} <-> {dpid}@{port}')

	def _bgworker_f(self):
		print('Refreshing Map')
		# print('\nAsking stats:')
		for dpid, _ in self.datapaths.list():
			ok, datapath,ofproto,parser = self.get_datapath(dpid)
			if ok:
				# print(f'  {dpid}')
				# req = parser.OFPFlowStatsRequest(datapath)
				# datapath.send_msg(req)
				req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
				datapath.send_msg(req)

		for link in get_all_link(self):
			# print(link)
			src = link.src.dpid
			dst = link.dst.dpid

			# Updating graph
			self.graph.add_arc(src, dst, link.src.port_no )
			ok, stats_data = self.portstats.get((link.src.dpid, link.src.port_no))
			if ok:
				# print(stats_data['data'])
				self.graph.update_weight(src, dst, stats_data['data'].tx_bytes, stats_data['data'].duration_sec)
			else:
				print(f'Stats {link.src.dpid}:{link.src.port_no} not found')
			# Pushing rule for multicast discarding
			ok, datapath,ofproto,parser = self.get_datapath(src)
			if ok:
				# print(f'Rejecting broadcast on {src}@{link.src.port_no}')
				match = parser.OFPMatch(
					eth_dst = mac.BROADCAST_STR,
					in_port = link.src.port_no)
				inst = [
					parser.OFPInstructionActions(ofproto.OFPIT_CLEAR_ACTIONS, [])
				]
				mod = parser.OFPFlowMod(
					datapath=datapath,
					table_id=1,
					priority=2,
					match=match,
					instructions=inst,
					hard_timeout = self.BGWORKER_THREAD_INTERVAL * 5
				)
				datapath.send_msg(mod)
			else:
				print(f'Datapath {dst} not found')


	def _bgworker_thread_f(self):
		while True:
			self._bgworker_f()
			hub.sleep(self.BGWORKER_THREAD_INTERVAL)
	
	def get_connection_id(self, src_ip, dst_ip, src_port, dst_port):
		return f'{src_ip}|{dst_ip}|{src_port}|{dst_port}'

	def _handle_pkt_tcp4(self, msg):
		datapath = msg.datapath
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser
		in_port = msg.match['in_port']

		pkt_in = packet.Packet(msg.data)
		eth_in = pkt_in.get_protocol(ethernet.ethernet)
		ipv4_in = pkt_in.get_protocol(ipv4.ipv4)
		tcp_in = pkt_in.get_protocol(tcp.tcp)
		
		# print("PKT DEBUG")
		# print(eth_in)
		# print(ipv4_in)
		# print(tcp_in)
		# print("END DEBUG")

		#print(f'---\nBEGIN handling TCP Connection\n---')
		dst_mac = eth_in.dst
		src_ip = ipv4_in.src
		dst_ip = ipv4_in.dst
		src_port = tcp_in.src_port
		dst_port = tcp_in.dst_port

		connection_id = self.get_connection_id(src_ip, dst_ip, src_port, dst_port)
		ok, _ = self.connections.get(connection_id)
		if (not ok):
			print(f'Got new Connection {connection_id} to {dst_mac} ', end='')

			ok, dp_data = self.host_dp_assoc.get(dst_mac)
			if (ok):
				dst_dpid = dp_data['dpid']
				dst_port = dp_data['port']
				print(f'for datapath {dst_dpid}@{dst_port}')

				# Computing shortest path
				path = self.graph.get_shortest_path(datapath.id, dst_dpid)
				hops = self.graph.path_to_hops(path)

				# Adding last hop (not included by path_to_hops)
				hops[dst_dpid] = {'port': dst_port}

				print(f'Routing through ')
				for item in path:
					dp_out_port = hops[item]["port"]
					print(f'	{hex(item)}@{dp_out_port}', end='')

					# Pushing rule to switch
					ok, tmp_datapath,tmp_ofproto,tmp_parser = self.get_datapath(item)
					if ok:
						match = tmp_parser.OFPMatch(
							eth_type=ether_types.ETH_TYPE_IP,
							ip_proto=inet.IPPROTO_TCP,
							ipv4_src=src_ip,
							ipv4_dst=dst_ip,
							# tcp_src=src_port,
							# tcp_dst=dst_port,
						)
						inst = [
							tmp_parser.OFPInstructionActions(
								tmp_ofproto.OFPIT_APPLY_ACTIONS, [
									tmp_parser.OFPActionOutput(dp_out_port)
								]
							)
						]
						mod = tmp_parser.OFPFlowMod(
							datapath=tmp_datapath,
							table_id=2,
							priority=20,
							match=match,
							instructions=inst,
							idle_timeout=1
						)
						tmp_datapath.send_msg(mod)
						print('[OK]')
					else:
						print(f'[KO] (Datapath not found')

				self.connections.set(connection_id, hops = hops)
			else:
				print(f'[KO] (datapath not found)')
		else:
			pass
			#print(f'Existing Connection')

		# In any case we need to route this packet via the controller
		ok, hops_data = self.connections.get(connection_id)
		if (ok):
			if (datapath.id in hops_data['hops']):
				dp_outport = hops_data['hops'][datapath.id]['port']

				print(f'Delivering TCP packet to port {dp_outport}', end='')

				out = parser.OFPPacketOut(
					datapath=datapath,
					buffer_id=msg.buffer_id,
					in_port=msg.match['in_port'],
					actions=[parser.OFPActionOutput(dp_outport)],
					data=msg.data
				)
				datapath.send_msg(out)
				print(f' OK')
			else:
				print(f'Datapath {datapath.id} not found in hops')
		else:
			print('Connection not found')

		#print(f'---\nEND handling TCP Connection\n---')
	def _handle_pkt_ipv6(self, msg):
		# Discarding
		return
		datapath = msg.datapath
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser
		in_port = msg.match['in_port']

		pkt_in = packet.Packet(msg.data)
		eth_in = pkt_in.get_protocol(ethernet.ethernet)
		ipv6_in = pkt_in.get_protocol(ipv6.ipv6)

		print(f'Dumping IPv6 PKT')
		self.dump(ipv6_in)
		self.dump(payload_a)
		self.dump(payload_b)

	# Return tuple (ok, datapath, ofproto, parser)
	def get_datapath(self, dpid):
		(ok, dp_data) = self.datapaths.get(dpid)
		if not ok:
			return (False, None, None, None)

		datapath = dp_data['ref']
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser
		return (True, datapath,ofproto,parser)

	def _send_pkt(self, data, dpid, port = None):
		(ok, datapath, ofproto, parser) = self.get_datapath(dpid)
		if not ok:
			print(f'Datapath {dpid} not found')
			return

		if port == None:
			port = ofproto.OFPP_FLOOD

		out = parser.OFPPacketOut(
			datapath=datapath,
			buffer_id=ofproto.OFP_NO_BUFFER,
			in_port=ofproto.OFPP_CONTROLLER,
			actions=[parser.OFPActionOutput(port)],
			data=data
		)
		# print(f'Sending pkt to {dst} via {dpid}@{port}')
		datapath.send_msg(out)

	def send_pkt(self, dst, data):
		(ok, route_data) = self.host_dp_assoc.get(dst)
		if not ok:
			print(f'Dest {dst} not found')
			return
		
		dpid = route_data['dpid']
		port = route_data['port']

		self._send_pkt(data, dpid, port)

	def broadcast_pkt(self, data, src=None):
		for dpid, _ in self.datapaths.list():
			self._send_pkt(data, dpid)

	@set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
	def _port_stats_reply_handler(self, ev):
		body = ev.msg.body
		for stat in body:
			self.portstats.set((ev.msg.datapath.id, stat.port_no), data = stat)
			
	@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
	def _packet_in_handler(self, ev):
		# print(f'MAIN DISPATCHER')
		msg = ev.msg
		datapath = msg.datapath
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser
		in_port = msg.match['in_port']

		pkt = packet.Packet(msg.data)
		eth_parsed = pkt.get_protocol(ethernet.ethernet)
		ipv4_parsed = pkt.get_protocol(ipv4.ipv4)

		# Detecting connected client
		self.add_node(eth_parsed.src, datapath.id, in_port)

		# print(eth.dst)

		# Discarding LLDP (already handled by ryu topology)
		if eth_parsed.ethertype == ether_types.ETH_TYPE_LLDP:
			# print(f'Discarding LLDP Packet')
			return
		# Discarding IPv6 (not handled by this script)
		if eth_parsed.ethertype == ether_types.ETH_TYPE_IPV6:
			# print(f'Discarding IPv6 Packet')
			return

		# Broadcasting Broadcast to all connected clients
		if (eth_parsed.dst == mac.BROADCAST_STR):
			print(f'Broadcast from {eth_parsed.src}')
			# print(msg.data)
			self.broadcast_pkt(msg.data, eth_parsed.src)
			return
		# Handling TCP Connections
		elif eth_parsed.ethertype == ether_types.ETH_TYPE_IP and ipv4_parsed != None and  ipv4_parsed.proto == inet.IPPROTO_TCP :
			self._handle_pkt_tcp4(msg)
		# Routing (through the controller) the remaining traffic
		else:
			print(f'Unicast from {eth_parsed.src} to {eth_parsed.dst}')
			self.send_pkt(eth_parsed.dst, msg.data)
			# dst = eth.dst
			# ok, dp = self.host_dp_assoc.get(dst)
			# if  ok :
			# 	self.send_pkt(msg.data, dp['dpid'], dp['port'])

		return











		# Discarding LLDP (already handled by ryu topology)
		if eth.ethertype == ether_types.ETH_TYPE_LLDP:
			# print(f'Discarding LLDP Packet')
			pass
		# # Proxying ARP request
		# elif eth.ethertype == ether_types.ETH_TYPE_ARP:
		# 	self._handle_pkt_arp(msg)

		# Handling IPv4 Packet
		elif eth.ethertype == ether_types.ETH_TYPE_IP:
			self._handle_pkt_ipv4(msg)
		# Ignoring IPv6 Packets
		elif eth.ethertype == ether_types.ETH_TYPE_IPV6:
			self._handle_pkt_ipv6(msg)
		# Routing unicast packet throw the controller
		elif eth.dst != mac.BROADCAST_STR:
			print(f'Unicast from {eth.src} to {eth.dst}')
			self.send_pkt(eth.dst, msg.data)
		# Logging unrecognized packets
		else:
			print(f'Unrecognized Packer')
			self.dump(pkt)
		# print(f'END MAIN DISPATCHER')

	@set_ev_cls(ofp_event.EventOFPErrorMsg)
	def error_msg_handler(self, ev):
		msg = ev.msg

		# print(f'!!!OFPErrorMsg!!! {msg.data.decode("ascii")}')
		print(msg)
		

	@set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
	def switch_features_handler(self, ev):
		# print(f'CONFIG DISPATCHER')
		
		datapath = ev.msg.datapath
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser

		# Adding datapath to config
		self.add_datapath(datapath)

		# # T0: Sending ARP Requests to the controller
		# match = parser.OFPMatch(
		# 	arp_op = arp.ARP_REQUEST
		# )
		# actions = [
		# 	parser.OFPActionOutput(
		# 		ofproto.OFPP_CONTROLLER,
		# 		ofproto.OFPCML_NO_BUFFER
		# 	)
		# ]
		# inst = [
		# 	parser.OFPInstructionActions(
		# 		ofproto.OFPIT_APPLY_ACTIONS,
		# 		actions
		# 	)
		# ]
		# mod = parser.OFPFlowMod(
		# 	datapath=datapath,
		# 	table_id=0,
		# 	priority=1,
		# 	match = match,
		# 	instructions=inst
		# )
		# datapath.send_msg(mod)

		# T0: Routing remaining traffic to the next table
		match = parser.OFPMatch()
		actions = []
		inst = [
			parser.OFPInstructionGotoTable(1)
		]
		mod = parser.OFPFlowMod(
			datapath=datapath,
			table_id=0,
			priority=0,
			match=match,
			instructions=inst
		)
		datapath.send_msg(mod)
   
   		# T1: Routing remaining traffic to the next table
		match = parser.OFPMatch()
		actions = []
		inst = [
			parser.OFPInstructionGotoTable(2)
		]
		mod = parser.OFPFlowMod(
			datapath=datapath,
			table_id=1,
			priority=0,
			match=match,
			instructions=inst
		)
		datapath.send_msg(mod)

   		# T2: Routing unmatched traffic through the controller
		match = parser.OFPMatch()
		actions = [
			parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,ofproto.OFPCML_NO_BUFFER)
		]
		inst = [
			parser.OFPInstructionActions(
				ofproto.OFPIT_APPLY_ACTIONS,
				actions
			)
		]
		mod = parser.OFPFlowMod(
			datapath=datapath,
			table_id=2,
			priority=1,
			match = match,
			instructions=inst
		)
		datapath.send_msg(mod)

		self._bgworker_f()
		# print(f'END CONFIG DISPATCHER')
   