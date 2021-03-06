import sys
import socket
import thread
import threading
from datetime import datetime
import time
from time import strftime
import struct
import os

# GLOBALS
connection_lock = threading.Lock()
max_segment_size = 576
packets = None
window = None
WIN_START = 0
WIN_END = 0
TOTAL_BYTES_SENT = 0
TOTAL_SEGMENTS_SENT = 0
TOTAL_SEGMENTS_RETRANSMITTED = 0
alpha = 0.125
beta = 0.25
sample_RTT= 1
estimated_RTT = 3
dev_RTT= 0
timeout_interval = estimated_RTT + 4 * dev_RTT
finished = False

def readfile(filename):
    packets = []
    try:
        statinfo = os.stat(filename)
        filesize = statinfo.st_size
        with open(filename, 'r') as f:
            for i in range(filesize // max_segment_size):
                packet = f.read(max_segment_size)
                packets.append(packet)
            packet = f.read(filesize % max_segment_size)
            packets.append(packet)
    except:
        print 'File not found'
        finished = True
        sys.exit(1)
    return packets

def write_logfile(log_filename, timestamp, source, destination, seq_num, ack_num, ack_flag, fin_flag, estimated_RTT):
    # timestamp, source, destination, Sequence #, ACK #, and the flags, and est_rtt
    logline = str(timestamp).ljust(25) + source.ljust(20) + destination.ljust(20) + str(seq_num).ljust(10) + \
              str(ack_num).ljust(10) + str(ack_flag).ljust(10) + str(fin_flag).ljust(10) + str(estimated_RTT).ljust(16) + '\n'

    if log_filename == 'stdout':
        print logline
    else:
        try:
            with open(log_filename, "a") as f:
                f.write(logline)
        except:
            print 'Logfile I/O error'

def make_packet(source_port, dest_port, seq_num, ack_num, ACK_flag, FIN_flag, window_size, checksum, datapacket):
    flagpart = makeflags(ACK_flag, FIN_flag)
    option = 0
    #To pack the header in a size of 20 bytes header and max_segment_size of segment
    header = struct.pack('!HHIIHHHH%ds' % len(datapacket), source_port, dest_port,
            seq_num, ack_num, flagpart, window_size, checksum, option, datapacket)
    return header

def makeflags(ackflag, finflag):
    if ackflag == 0 and finflag == 0:
        flagpart = 0
    elif ackflag == 0 and finflag == 1:
        flagpart = 1
    elif ackflag == 1 and finflag == 0:
        flagpart = 16
    elif ackflag == 1 and finflag == 1:
        flagpart = 17
    else:
        print('Invalid flags.')
        flagpart = 0
    return flagpart

def getflags(flags):
    if flags == 0:
        ackflag = 0
        finflag = 0
    elif flags == 1:
        ackflag = 0
        finflag = 1
    elif flags == 16:
        ackflag = 1
        finflag = 0
    elif flags == 17:
        ackflag = 1
        finflag = 1
    return ackflag, finflag

def transmit_packet(packet, seq_num, UDPsendsocket, UDP_ADDR):
    global connection_lock
    global window
    global TOTAL_BYTES_SENT
    global TOTAL_SEGMENTS_SENT
    TOTAL_BYTES_SENT += len(packet)
    TOTAL_SEGMENTS_SENT += 1
    UDPsendsocket.sendto(packet, UDP_ADDR)
    connection_lock.acquire()
    window[seq_num]['time'] = time.time()
    connection_lock.release()

def receive_ACK(ack_sock, recv_IP, log_filename):
    global connection_lock
    global max_segment_size
    global packets
    global window
    global WIN_START
    global WIN_END
    global alpha, beta, sample_RTT, estimated_RTT, dev_RTT, timeout_interval
    global finished

    try:
        while not finished:
            # wait for an ACK message
            try:
                ACK = ack_sock.recvfrom(1024)
            except:
                print 'Error receiving ACK'
                finished = True
                sys.exit(1)

            string_size = len(ACK[0]) - 20 # for the header
            received = struct.unpack('!HHIIHHHH%ds' % string_size, ACK[0])
            (source_port, dest_port, seq_num, ack_num, flagpart,
                    window_size, checksum, option, datachunk) = received
            ack_flag, fin_flag = getflags(flagpart)
            # ACKed properly
            if ack_flag:
                connection_lock.acquire()
                window[ack_num]['ack'] = True
                connection_lock.release()
            # NAKed
            else:
                pass
            sample_RTT = time.time() - window[ack_num]['time']
            estimated_RTT = (1 - alpha) * estimated_RTT + alpha * sample_RTT
            dev_RTT = (1 - beta) * dev_RTT + beta * abs(sample_RTT - estimated_RTT)
            timeout_interval = estimated_RTT + 4 * dev_RTT

            # log the ACK
            timestamp = datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
            source = recv_IP
            destination = socket.gethostbyname(socket.gethostname())
            write_logfile(log_filename, timestamp, source, destination, seq_num, ack_num, ack_flag, fin_flag, estimated_RTT)
    except KeyboardInterrupt:
        sys.exit(1)

def checksum_verify(input_data):
    total = 0
    for num in range(len(input_data)):
        total += ord(input_data[num]) << 8 if num % 2 == 0 else ord(input_data[num])
    return total % 65536

def main():
    global connection_lock
    global max_segment_size
    global packets
    global window
    global WIN_START
    global WIN_END
    global TOTAL_BYTES_SENT
    global TOTAL_SEGMENTS_SENT
    global TOTAL_SEGMENTS_RETRANSMITTED
    global alpha, beta, sample_RTT, estimated_RTT, dev_RTT, timeout_interval
    global finished
    if(len(sys.argv) != 6 and len(sys.argv) != 7):
        print 'Usage:'
        print 'python sender.py <filename> <remote_IP> <remote_port> <ack_port_num> <log_filename> [<window_size>]'
        finished = True
        sys.exit()
    filename = sys.argv[1]
    try:
        recv_IP = socket.gethostbyname(sys.argv[2])
    except:
        print 'remote_IP error'
        finished = True
        sys.exit(1)
    try:
        recv_port = int(sys.argv[3])
    except ValueError:
        print '<recv_port> is an integer.'
        finished = True
        sys.exit(1)
    try:
        ack_port_num = int(sys.argv[4])
    except ValueError:
        print '<ack_port_num> is an integer.'
        finished = True
        sys.exit(1)
    log_filename = sys.argv[5]
    try:
        window_size = int(sys.argv[6])
    except ValueError:
        print '<window_size> is an integer'
        finished = True
        sys.exit(1)
    except:
        window_size = 1
    window_size = 1
    # write the labels on the logfile
    write_logfile(log_filename, 'timestamp', 'source', 'destination', 'seq_num', 'ack_num', 'ack_flag', 'fin_flag', 'est_RTT')
    # UDP socket for SENDING DATA
    UDPsendsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    UDP_SEND_ADDR = (recv_IP, recv_port)
    # UDP socket for RECEIVING ACKs
    UDPacksocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    UDPackhost = socket.gethostbyname(socket.gethostname())
    UDP_ACK_ADDR = (UDPackhost, ack_port_num)
    try:
        UDPacksocket.bind(UDP_ACK_ADDR)
    except socket.error, msg:
        print 'Failed to bind socket. Error code ['+str(msg[0])+'] Error message:'+msg[1]
        finished = True
        sys.exit()
    # send it into its own thread
    ack_thread = threading.Thread(target = receive_ACK, args = (UDPacksocket, recv_IP, log_filename))
    ack_thread.setDaemon(True)
    ack_thread.start()

    # CREATE THE WINDOW
    packets = readfile(filename)
    window = [{'ack': False, 'time': None} for seq in range(len(packets))]
    WIN_START = 0
    WIN_END = window_size - WIN_START

    window_fully_acked = False
    try:
        while not (window_fully_acked and WIN_END == len(window)):
            window_fully_acked = True
            for packet_idx in range(WIN_START, WIN_END):

                # check to see if the beginning of the window has been ACKED and we aren't at the end of the window.
                # if we're not at the end of the window, then move the pointers over to the
                # right and proceed. If we're at the end, then we
                # must keep looping until the entire window is fully acked
                if window[WIN_START]['ack'] and WIN_END < len(window):
                    WIN_START += 1
                    WIN_END += 1
                    packet = packets[packet_idx]
                    ACK_NUM = 0
                    ACK_FLAG = 1
                    # 1 if it's the last packet
                    FIN_FLAG = 0 if packet_idx < len(packets) - 1 else 1
                    sumstring =  make_packet(ack_port_num, recv_port, packet_idx, ACK_NUM,
                            ACK_FLAG, FIN_FLAG, window_size, 0, packet)
                    checksum = checksum_verify(sumstring)
                    sendpacket = make_packet(ack_port_num, recv_port, packet_idx, ACK_NUM,
                            ACK_FLAG, FIN_FLAG, window_size, checksum, packet)
                    try:
                        transmit_packet(sendpacket, packet_idx, UDPsendsocket, UDP_SEND_ADDR)
                    except socket.error, msg:
                        print 'socket error code ['+str(msg[0])+'], error message: '+str(msg[1])
                        finished = True
                        sys.exit()
                    # log the sent packet
                    timestamp = datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
                    source = socket.gethostbyname(socket.gethostname())
                    destination = recv_IP
                    write_logfile(log_filename, timestamp, source, destination, packet_idx, ACK_NUM, ACK_FLAG, FIN_FLAG, estimated_RTT)
                    window_fully_acked = False if FIN_FLAG == 0 else True
                    break

                if not window[packet_idx]['ack']:
                    window_fully_acked = False

                # if packet hasn't been sent or packet timed out, (re)send packet
                if window[packet_idx]['time'] is None or \
                        time.time() - window[packet_idx]['time'] > timeout_interval:
                    packet = packets[packet_idx]
                    # whatever, it's the sender
                    ACK_NUM = 0
                    ACK_FLAG = 1
                    # 1 if it's the last packet
                    FIN_FLAG = 0 if packet_idx < len(packets) - 1 else 1
                    sumstring =  make_packet(ack_port_num, recv_port, packet_idx, ACK_NUM,
                            ACK_FLAG, FIN_FLAG, window_size, 0, packet)
                    checksum = checksum_verify(sumstring)
                    sendpacket = make_packet(ack_port_num, recv_port, packet_idx, ACK_NUM,
                            ACK_FLAG, FIN_FLAG, window_size, checksum, packet)
                    # if retransmitting (which means that the 'time' has already been set
                    if window[packet_idx]['time'] is not None:
                        TOTAL_SEGMENTS_RETRANSMITTED += 1
                    try:
                        transmit_packet(sendpacket, packet_idx, UDPsendsocket, UDP_SEND_ADDR)
                    except socket.error, msg:
                        print 'socket error code ['+str(msg[0])+'], error message: '+str(msg[1])
                        finished = True
                        sys.exit()

                    # log the sent packet
                    timestamp = datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
                    source = socket.gethostbyname(socket.gethostname())
                    destination = recv_IP
                    write_logfile(log_filename, timestamp, source, destination, packet_idx, ACK_NUM, ACK_FLAG, FIN_FLAG, estimated_RTT)

    except KeyboardInterrupt:
        finished = True
        sys.exit(1)
    finished = True
    print(('Delivery completed successfully\n'+
            'Total bytes sent: %d\n'+
            'Segments sent: %d\n'+
            'Segments retransmitted: %f\n') % (TOTAL_BYTES_SENT,
                                               TOTAL_SEGMENTS_SENT,
                                               float(TOTAL_SEGMENTS_RETRANSMITTED) / TOTAL_SEGMENTS_SENT))

if __name__ == '__main__':
    main()
