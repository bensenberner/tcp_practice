import sys
import socket
import thread
from threading import Thread
import time
from time import strftime
import struct

MAXSEGMENTSIZE = 576                   # File will be divided into this size of segments to be transferred
FIRST_CORRUPTION = False               # The flag of first receiving
ACK_ACK = 0                            # ACK # used to send ACK back to sender
ACK_SEQUENCE = 0                       # Sequence # used to send ACK back to sender
TRANS_FINISH = False                   # The flag to mark if the transmission is finished

def rft_header(source_port, dest_port, seq_num, ack_num, ACK_flag, FIN_flag, window_size, checksum, datachunk):
    "To pack the reliable file transfer data with TCP-like header"

    #To determine the value of flag part in the header
    if ACK_flag == 0 and FIN_flag == 0:
        flagpart = 0         #0x0000
    elif ACK_flag == 0 and FIN_flag == 1:
        flagpart = 1         #0x0001
    elif ACK_flag == 1 and FIN_flag == 0:
        flagpart = 16        #0x0010
    elif ACK_flag == 1 and FIN_flag == 1:
        flagpart = 17        #0x0011

    option = 0
    #To pack the header in a size of 20 bytes header and MAXSEGMENTSIZE of segment
    header = struct.pack('!HHIIHHHH%ds' % len(datachunk), source_port, dest_port,
            seq_num, ack_num, flagpart, window_size, checksum, option, datachunk)

    return header

def checksum_verify(old_datagram):
    string_size = len(receiveddata[0]) - 20 # for the header
    received = struct.unpack('!HHIIHHHH%ds' % string_size, receiveddata[0])
    (sender_port, recv_port, seq_num, ack_num, flagpart,
            window_size, checksum, option, datachunk) = received

    string_size = len(old_datagram) - 20 # for the header
    original_packet = struct.unpack('!HHIIHHHH%ds' % string_size, old_datagram)
    (sender_port, recv_port, seq_num, ack_num, flagpart,
            window_size, checksum, option, datachunk) = original_packet

    # set checksum to 0 to reconstruct original checksum calculation
    new_packet = struct.pack('!HHIIHHHH%ds' % string_size, sender_port, recv_port,
            seq_num, ack_num, flagpart, window_size, 0, option, datachunk)

    "To verify the received data"
    sum_calc = 0

    #Divide the string by 16 bits and calculate the sum
    for num in range(len(new_packet)):
        if num % 2 == 0:    # Even parts with higher order
            sum_calc += (ord(new_packet[num]) << 8)
        else:               # Odd parts with lower order
            sum_calc += ord(new_packet[num])

    # Get the inverse as the checksum
    output_sum = (sum_calc % 65536)

    return output_sum == checksum

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

if __name__ == '__main__':
    #Invoke the program to import <filename>, <listening_port>, <sender_IP>, <sender_ack_port> and <log_filename>
    if(len(sys.argv) != 6):
        print 'Please follow the format to invoke the program:'
        print 'python receiver.py <filename> <listening_port> <sender_IP> <sender_ack_port> <log_filename>'
        sys.exit()
    filename = sys.argv[1]
    try:
        listening_port = int(sys.argv[2])
    except ValueError:
        print '<listening_port> should be an integrate.'
        sys.exit()
    sender_IP = sys.argv[3]
    try:
        sender_ack_port = int(sys.argv[4])
    except ValueError:
        print '<sender_ack_port> should be an integrate.'
        sys.exit()
    log_filename = sys.argv[5]

    # set up a UDP socket for sending ACKs
    UDP_ack_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # TODO: change this
    # UDP_ACK_HOST = sender_IP
    UDP_ACK_HOST = '127.0.0.1'
    UDP_ACK_PORT = sender_ack_port
    UDP_ACK_ADDR = (UDP_ACK_HOST, UDP_ACK_PORT)

    #To set up a UDP socket for receiving the data
    UDP_recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # UDP_HOST = socket.gethostbyname(socket.gethostname())
    # TODO: change this
    UDP_RECV_HOST = '127.0.0.1'
    # UDP_RECV_HOST = socket.gethostbyname(socket.gethostname())
    UDP_RECV_PORT = listening_port
    UDP_RECV_ADDR = (UDP_RECV_HOST, UDP_RECV_PORT)

    try:
        UDP_recv_socket.bind(UDP_RECV_ADDR)
    except socket.error, msg:
        print 'Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
        sys.exit()

    print '>> Waiting for sender invoking...'
    #Receive first data and check the packet
    receiveddata = UDP_recv_socket.recvfrom(1024)
    string_size = len(receiveddata[0]) - 20 # for the header
    received = struct.unpack('!HHIIHHHH%ds' % string_size, receiveddata[0])
    (sender_port, recv_port, seq_num, ack_num, flagpart,
            window_size, checksum, option, datachunk) = received
    ackflag, finflag = getflags(flagpart)

    # TODO: write the first data

    RCV_SEQ_NUM = 0
    while finflag != 1:
        receiveddata = UDP_recv_socket.recvfrom(1024)
        string_size = len(receiveddata[0]) - 20 # for the header
        # TODO:
        received = struct.unpack('!HHIIHHHH%ds' % string_size, receiveddata[0])
        (sender_port, recv_port, seq_num, ack_num, flagpart,
                window_size, checksum, option, datachunk) = received
        ackflag, finflag = getflags(flagpart)
        # if checksum is good
        if checksum_verify(receiveddata[0]):
            # check the sequence number
            if seq_num == RCV_SEQ_NUM:
            # source_port, dest_port, seq_num, ack_num, ACK_flag, FIN_flag, window_size, checksum, datachunk
                # packet = rft_header('127.0.0.1',
                # increment receiver seq num
                # TODO: make these real
                ACK_FLAG = 1
                FIN_FLAG = 0
                rft_checksum = 0
                # RCV_SEQ_NUM = (RCV_SEQ_NUM + 1) % window_size
                RCV_SEQ_NUM += 1
                packet = ''
                sendpacket = rft_header(recv_port, sender_port, RCV_SEQ_NUM,
                    seq_num, ACK_FLAG, FIN_FLAG, window_size, rft_checksum, packet)

                # write the data to the file
                with open(filename, 'a') as f:
                    f.write(datachunk)

                # send the ACK
                try:
                    UDP_ack_socket.sendto(sendpacket, UDP_ACK_ADDR)
                except socket.error, msg:
                    print 'Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
                    sys.exit()

            # TODO: make sure this works
            # if its a lower seq num than expected, just ACK
            elif seq_num < RCV_SEQ_NUM:
                # send an ack for that
                # ACK_FLAG = 1
                # FIN_FLAG = 0
                # rft_checksum = 0
                # # RCV_SEQ_NUM = (RCV_SEQ_NUM + 1) % window_size
                # RCV_SEQ_NUM += 1
                # packet = ''
                # sendpacket = rft_header(recv_port, sender_port, seq_num,
                #     seq_num, ACK_FLAG, FIN_FLAG, window_size, rft_checksum, packet)
                pass

            # else drop the packet
            else:
                pass

        # else if checksum is bad
        else:
            pass
