import sys
import socket
import thread
import threading
import time
from time import strftime
import struct
import os

# GLOBALS
connection_lock = threading.Lock()
MAXSEGMENTSIZE = 576
packets = None
window = None
WIN_START = 0
WIN_END = 0

def readfile(filename):
    "To read the data that will be sent from the file"
    packets = []
    try:
        statinfo = os.stat(filename)
        filesize = statinfo.st_size
        with open(filename, 'r') as f:

            for i in range(filesize // MAXSEGMENTSIZE):
                packet = f.read(MAXSEGMENTSIZE)
                packets.append(packet)

            packet = f.read(filesize % MAXSEGMENTSIZE)
            packets.append(packet)
    except:
        print 'File not found'
        sys.exit(1)

    return packets

def make_packet(source_port, dest_port, seq_num, ack_num, ACK_flag, FIN_flag, window_size, checksum, datapacket):
    "To pack the reliable file transfer data with TCP-like header"
    flagpart = makeflags(ACK_flag, FIN_flag)
    option = 0
    #To pack the header in a size of 20 bytes header and MAXSEGMENTSIZE of segment
    header = struct.pack('!HHIIHHHH%ds' % len(datapacket), source_port, dest_port,
            seq_num, ack_num, flagpart, window_size, checksum, option, datapacket)

    return header

def makeflags(ackflag, finflag):
    if ackflag == 0 and finflag == 0:
        flagpart = 0         #0x0000
    elif ackflag == 0 and finflag == 1:
        flagpart = 1         #0x0001
    elif ackflag == 1 and finflag == 0:
        flagpart = 16        #0x0010
    elif ackflag == 1 and finflag == 1:
        flagpart = 17        #0x0011
    else:
        print('invalid flags')
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
    UDPsendsocket.sendto(packet, UDP_ADDR)
    connection_lock.acquire()
    window[seq_num]['time'] = time.time()
    connection_lock.release()

def dealWithACK(ack_sock):
    global connection_lock
    global MAXSEGMENTSIZE
    global packets
    global window
    global WIN_START
    global WIN_END

    # TODO: make some kind of indicator to show when there are no more ACKs
    # to be received. Perhaps you should move the logic to increment the window
    # pointers to within here?
    while True:
        # wait for an ACK message
        try:
            ACK = ack_sock.recvfrom(1024)
        except:
            print 'Error receiving ACK'
            sys.exit(1)

        string_size = len(ACK[0]) - 20 # for the header
        received = struct.unpack('!HHIIHHHH%ds' % string_size, ACK[0])
        (source_port, dest_port, seq_num, ack_num, flagpart,
                window_size, checksum, option, datachunk) = received
        ackflag, finflag = getflags(flagpart)
        if ackflag:
            connection_lock.acquire()
            window[ack_num]['ack'] = True
            connection_lock.release()

def checksum_verify(sumstring):
    "To verify the received data"
    sum_calc = 0

    #Divide the string by 16 bits and calculate the sum
    for num in range(len(sumstring)):
        if num % 2 == 0:     # Even parts with higher order
            sum_calc = sum_calc + (ord(sumstring[num]) << 8)
        elif num % 2 == 1:   # Odd parts with lower order
            sum_calc = sum_calc + ord(sumstring[num])

    # Get the inverse as the checksum
    output_sum = (sum_calc % 65536)

    return output_sum

def main():
    global connection_lock
    global MAXSEGMENTSIZE
    global packets
    global window
    global WIN_START
    global WIN_END

    #Invoke the program to import <filename>, <recv_IP>, <recv_port>, <ack_port_num>, <log_filename> and <window_size>
    if(len(sys.argv) != 6 and len(sys.argv) != 7):
        print 'Please follow the format to invoke the program:'
        print 'python sender.py <filename> <recv_IP> <recv_port> <ack_port_num> <log_filename> <window_size>'
        print '<window_siz> is optional'
        sys.exit()

    filename = sys.argv[1]
    recv_IP = sys.argv[2]

    #Check the integer values
    try:
        recv_port = int(sys.argv[3])
    except ValueError:
        print '<recv_port> should be an integer.'
        sys.exit()
    try:
        ack_port_num = int(sys.argv[4])
    except ValueError:
        print '<ack_port_num> should be an integer.'
        sys.exit()
    log_filename = sys.argv[5]
    #Choose a window_size from command, otherwise using a default value
    try:
        window_size = int(sys.argv[6])
    except ValueError:
        print '<window_size> should be an integrate'
        sys.exit()
    except:
        window_size = 1

    # UDP socket for SENDING DATA
    UDPsendsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    UDP_SEND_HOST = recv_IP
    UDP_SEND_PORT = recv_port
    UDP_SEND_ADDR = (UDP_SEND_HOST, UDP_SEND_PORT)

    # UDP socket for RECEIVING ACKs
    UDPacksocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # TODO: do not hardcode this.
    try:
        UDPacksocket.bind((UDP_SEND_HOST, ack_port_num))
    except socket.error, msg:
        print 'Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
        sys.exit()
    # send it into its own thread
    ack_thread = threading.Thread(target = dealWithACK, args = (UDPacksocket,))
    ack_thread.setDaemon(True)
    ack_thread.start()

    # TODO: checksum shit
    # sumstring = make_packet(rft_sender.recv_port, rft_sender.ack_port_num, SEQUENCE_NUM, ACK_NUM, 1, 0, 0, rft_sender.total_sending_message[SENDINGPOINTER])
    # rft_checksum = checksum_calc(sumstring)
    # sendpacket = make_packet(rft_sender.recv_port, rft_sender.ack_port_num, SEQUENCE_NUM, ACK_NUM, 1, 0, rft_checksum, rft_sender.total_sending_message[SENDINGPOINTER])

    # CREATE THE WINDOW
    packets = readfile(filename)
    window = [{'ack': False, 'time': None} for seq in range(len(packets))]
    WIN_START = 0
    WIN_END = window_size - WIN_START

    # TODO: UPDATE THE TIMEOUT VARIABLE!!!
    # this is in seconds
    TIME_OUT = 3

    window_fully_acked = False
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

                # send the newest packet
                packet = packets[packet_idx]
                # whatever, it's the sender
                ACK_NUM = 0
                ACK_FLAG = 1
                # 1 if it's the last packet
                FIN_FLAG = 0 if packet_idx < len(packets) - 1 else 1
                # TODO: make this real
                sumstring =  make_packet(ack_port_num, recv_port, packet_idx, ACK_NUM,
                        ACK_FLAG, FIN_FLAG, window_size, 0, packet)
                checksum = checksum_verify(sumstring)
                print(checksum)
                sendpacket = make_packet(ack_port_num, recv_port, packet_idx, ACK_NUM,
                        ACK_FLAG, FIN_FLAG, window_size, checksum, packet)
                try:
                    transmit_packet(sendpacket, packet_idx, UDPsendsocket, UDP_SEND_ADDR)
                except socket.error, msg:
                    print 'Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
                    sys.exit()
                window_fully_acked = False
                break

            if not window[packet_idx]['ack']:
                window_fully_acked = False

            # if packet hasn't been sent or packet timed out, resend packet
            if window[packet_idx]['time'] is None or \
                    time.time() - window[packet_idx]['time'] > TIME_OUT:
                packet = packets[packet_idx]
                # whatever, it's the sender
                ACK_NUM = 0
                ACK_FLAG = 1
                # 1 if it's the last packet
                FIN_FLAG = 0 if packet_idx < len(packets) - 1 else 1
                # TODO: make this real
                sumstring =  make_packet(ack_port_num, recv_port, packet_idx, ACK_NUM,
                        ACK_FLAG, FIN_FLAG, window_size, 0, packet)
                checksum = checksum_verify(sumstring)
                print(checksum)
                sendpacket = make_packet(ack_port_num, recv_port, packet_idx, ACK_NUM,
                        ACK_FLAG, FIN_FLAG, window_size, checksum, packet)
                try:
                    transmit_packet(sendpacket, packet_idx, UDPsendsocket, UDP_SEND_ADDR)
                except socket.error, msg:
                    print 'Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
                    sys.exit()

if __name__ == '__main__':
    main()
