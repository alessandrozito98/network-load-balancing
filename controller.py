# Assuming topology discovery (ryu-manager --observe-links)
# Assuming switch topology doesn't change over time

# Table 0 is for handling ARP (and similar) traffic
# - ARP requests are handled by the controller
# - Non-IP packets are discarded (?)
# - Remaining traffic is directed to the next table

# Table 1 is for handling defined routes
# - Each time a new connection is detected the specific route for that is computed by the controller and pushed in this table
# - Unmatched packets will be directed to the controller

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3, inet
from ryu.lib.packet import packet, ethernet, arp, lldp, ipv4, ipv6, tcp, ether_types
from ryu.lib import hub
from ryu.topology import event, switches
from ryu.topology.api import get_all_switch, get_all_link, get_all_host
import networkx as nx 

from threading import Lock

class WeightedLoadBalancer(app_manager.RyuApp):
	OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
	MAPPER_THREAD_INTERVAL = 1
	net_mutex = Lock()

	def __init__(self, *args, **kwargs):
		super(WeightedLoadBalancer, self).__init__(*args, **kwargs)

		# Weighted network map
		self.net = nx.DiGraph()

		# Mac Table
		self.macs = {}

		# Datapath Table
		self.datapaths = {}
		
		# thread che lancia periodicamente le richieste
		# self.monitor_thread = hub.spawn(self._monitor)
		self.net_mapper_thread = hub.spawn(self._net_mapper_thread_f)

	def dump(self, obj):
		attrs = vars(obj)
		print(', '.join("%s: %s\n" % item for item in attrs.items()))

	def net_update_weight(self, datapath, port, updateId, totalLoad):
		# Computing src and desc id
		src = datapath.id
		dst = self.datapaths[src][port]
		assert dst != None

		self.net_mutex.acquire()
		link = self.net[src][dst]
		assert link != None

		interval = updateId - link.updateId
		if (interval < 0):
			return  #Old Update
		
		link.weight = totalLoad - link.totalLoad
		link.totalLoad = totalLoad
		self.net_mutex.release()

	def net_get_shortest(self, start, end):
		self.net_mutex.acquire()
		self.net_mutex.release()

	def _net_mapper_thread_f(self):
		while True:
			
			self.net_mutex.acquire()
			# print('Updating map')
			for switch in get_all_switch(self):
				name = f'dp-{switch.dp.id}'
				if (not self.net.has_node(name)):
					self.net.add_node(name, ref=switch, type='datapath')
					print(f'Discovered new datapath {name}')
				
			for link in get_all_link(self):
				src_name = f'dp-{link.src.dpid}'
				dst_name= f'dp-{link.dst.dpid}'
				if (not self.net.has_edge(src_name, dst_name)):
					self.net.add_edge(src_name, dst_name, port=link.src.port_no)
					print(f'Discovered new link {src_name} -> {dst_name} @ {link.src.port_no}')
			
			for host in get_all_host(self):
				host_name = f'h-{host.mac}'
				dp_name = f'dp-{host.port.dpid}'
				port = host.port.port_no

				# Updating Map
				if (not self.net.has_node(host_name)):
					self.net.add_node(host_name, ref=host, type='host')
					self.net.add_edge(host_name, dp_name, port=port)
					self.net.add_edge(dp_name, host_name, port=port)
					print(f'Discovered new host {host_name} <-> {dp_name} @ {port}')
				
			self.net_mutex.release()

			hub.sleep(self.MAPPER_THREAD_INTERVAL)
			
	def _refresh_mac_assoc(self): 
		print('Refreshing Mac')
		for host in get_all_host(self):
			for ip in (host.ipv4 + host.ipv6):
				mac = host.mac
				if (not ip in self.macs):
					print(f'Discovered new IP {ip} <-> {mac}')
					self.macs[ip] = mac

	def _handle_pkt_ipv4(self, msg):
		datapath = msg.datapath
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser
		in_port = msg.match['in_port']

		pkt_in = packet.Packet(msg.data)
		eth_in = pkt_in.get_protocol(ethernet.ethernet)
		ipv4_in = pkt_in.get_protocol(ipv4.ipv4)

		# Handling only TCP Connections
		if ipv4_in.proto == inet.IPPROTO_TCP:
			tcp_in = pkt_in.get_protocol(tcp.tcp)
			print('Dumping TCP PKT')
			self.dump(ipv4_in)
			self.dump(tcp_in)

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

		print('Dumping IPv6 PKT')
		self.dump(ipv6_in)
		self.dump(payload_a)
		self.dump(payload_b)

	def _handle_pkt_arp(self, msg):
		datapath = msg.datapath
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser
		in_port = msg.match['in_port']

		pkt_in = packet.Packet(msg.data)
		eth_in = pkt_in.get_protocol(ethernet.ethernet)
		arp_in = pkt_in.get_protocol(arp.arp)

		if arp_in.opcode != arp.ARP_REQUEST:
			return

		dst_ip = arp_in.dst_ip

		self._refresh_mac_assoc()

		print (f'Resolving ARP Request for {dst_ip} on {datapath.id}@{in_port} ', end='')
		if (dst_ip in self.macs):
			destination_host_mac = self.macs[dst_ip]
			print(f'with MAC {destination_host_mac}')

			pkt_out = packet.Packet()
			eth_out = ethernet.ethernet(
				dst = eth_in.src,
				src = destination_host_mac,
				ethertype = ether_types.ETH_TYPE_ARP
			)
			arp_out = arp.arp(
				opcode  = arp.ARP_REPLY,
				src_mac = destination_host_mac,
				src_ip  = arp_in.dst_ip,
				dst_mac = arp_in.src_mac,
				dst_ip  = arp_in.src_ip
			)
			pkt_out.add_protocol(eth_out)
			pkt_out.add_protocol(arp_out)
			pkt_out.serialize()

			out = parser.OFPPacketOut(
				datapath=datapath,
				buffer_id=ofproto.OFP_NO_BUFFER,
				in_port=ofproto.OFPP_CONTROLLER,
				actions=[parser.OFPActionOutput(in_port)],
				data=pkt_out.data
			)
			datapath.send_msg(out)
		else:
			print('... KO')
			# print('Forwarding ARP request to ', end='')
			# nodes = self.net.nodes(data=True)
			# for (dp_id, dp_data) in nodes:
			# 	if data['type'] == 'datapath':
			# 		print(dp_id)
			# 		print(dp_data)
			# 		print(self.net[dp_id])
			# 		for nb_id in self.net[dp_id]:
			# 			print(f'---{nb_id}')
			# 			nb_data = nodes[nb_id]
			# 			if (nb_data['type'] == 'host'):
			# 				print(f'Forwarding Request to {nb_id} via {dp_id}@{dp_data')

			# 			# if self.net[neighbor]['type'] == 'host':
			# 			# 	print(neighbor)
			# 			# else :
			# 			# 	print('nah')

			# 		print('')
		return
   
	@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
	def _packet_in_handler(self, ev):
		# print('MAIN DISPATCHER')
		msg = ev.msg
		datapath = msg.datapath
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser
		in_port = msg.match['in_port']

		pkt = packet.Packet(msg.data)
		eth = pkt.get_protocol(ethernet.ethernet)

		# Discarding LLDP (already handled by ryu topology)
		if eth.ethertype == ether_types.ETH_TYPE_LLDP:
			pass

		# Proxying ARP request
		elif eth.ethertype == ether_types.ETH_TYPE_ARP:
			self._handle_pkt_arp(msg)

		# Handling IPv4 Packet
		elif eth.ethertype == ether_types.ETH_TYPE_IP:
			self._handle_pkt_ipv4(msg)
		# Ignoring IPv6 Packets
		elif eth.ethertype == ether_types.ETH_TYPE_IPV6:
			self._handle_pkt_ipv6(msg)
		# Logging unrecognized packets
		else:
			self.dump(pkt)
		# print('END MAIN DISPATCHER')
	@set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
	def switch_features_handler(self, ev):
		# print('CONFIG DISPATCHER')
		datapath = ev.msg.datapath
		ofproto = datapath.ofproto
		parser = datapath.ofproto_parser

		# T0: Sending ARP Requests to the controller
		match = parser.OFPMatch(
			arp_op = arp.ARP_REQUEST
		)
		actions = [
			parser.OFPActionOutput(
				ofproto.OFPP_CONTROLLER,
				ofproto.OFPCML_NO_BUFFER
			)
		]
		inst = [
			parser.OFPInstructionActions(
				ofproto.OFPIT_APPLY_ACTIONS,
				actions
			)
		]
		mod = parser.OFPFlowMod(
			datapath=datapath,
			table_id=0,
			priority=1,
			match = match,
			instructions=inst
		)
		datapath.send_msg(mod)

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
   
   		# T1: Routing unmatched traffic through the controller
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
			table_id=1,
			priority=1,
			match = match,
			instructions=inst
		)
		datapath.send_msg(mod)
   
		# print('END CONFIG DISPATCHER')
   
   
   
   
   
   
   
   
   
   
   
	# # trova switch destinazione e porta dello switch
	# def find_destination_switch(self,destination_mac):
	# 	for host in get_all_host(self):
	# 		if host.mac == destination_mac:
	# 			return (host.port.dpid, host.port.port_no)
	# 	return (None,None)

	# def find_next_hop_to_destination(self,source_id,destination_id):
	# 	net = nx.DiGraph()
	# 	for link in get_all_link(self):
	# 		net.add_edge(link.src.dpid, link.dst.dpid, port=link.src.port_no, updateId=0, weight=0, totalLoad=0)

	# 	path = nx.shortest_path(
	# 		net,
	# 		source_id,
	# 		destination_id
	# 	)

	# 	first_link = net[ path[0] ][ path[1] ]

	# 	return first_link['port']


	

	# execute at switch registration
	# By default we send all packets in flood while we learn the right path
	
