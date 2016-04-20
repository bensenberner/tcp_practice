#---------------------Source Import--------------------
import sys
import socket
import thread
from threading import Thread
import time
from time import strftime
import struct

#------------------------Variables---------------------
MAXSEGMENTSIZE = 576                   # File will be divided into this size of segments to be transferred
FIRST_CORRUPTION = False               # The flag of first receiving
ACK_ACK = 0                            # ACK # used to send ACK back to sender
ACK_SEQUENCE = 0                       # Sequence # used to send ACK back to sender
TRANS_FINISH = False                   # The flag to mark if the transmission is finished

#-------------------------Classes----------------------
class Receiver:
    'The class used to describe the receiver'

    def __init__(self, wrto_file, listening_port, sender_IP, sender_ack_port, log_file):
        "To initialize the class with variables"
        self.wrto_filename = wrto_file
        self.listening_port = listening_port
        self.sender_IP = sender_IP
        self.sender_ack_port = sender_ack_port
        self.log_filename = log_file

    def displayReceiver(self):
        "To display the variables of the class (just for testing)"

        print 'Saved filename:'.ljust(30), self.wrto_filename
        print 'Receiver side log filename:'.ljust(30), self.log_filename
        print 'Sender IP:'.ljust(30), self.sender_IP
        print 'Sender port:'.ljust(30), self.sender_ack_port
        print 'Receiver listening port:'.ljust(30), self.listening_port

    def filewriting(self, data):
        "To write received data to the file"

        # Open the file from the name specified in the command line
        try:
            # TODO: shouldn't this be a binary write
            Datafile = open(self.wrto_filename,"a")
            Datafile.write(data)
            Datafile.close()
        except:
            print 'File not found'

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

    #To pack the header in a size of 20 bytes header and MAXSEGMENTSIZE of segment
    header = struct.pack('!HHIIHHHH%ds' % \
            len(datachunk),
            source_port,
            dest_port,
            seq_num,
            ack_num,
            flagpart,
            window_size,
            checksum,
            0,
            datachunk)

    return header

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

    #Initialization of the object of Receiver class
    rft_receiver = Receiver(filename, listening_port, sender_IP, sender_ack_port, log_filename)

    # set up a UDP socket for sending ACKs
    UDP_ack_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # TODO: change this
    UDP_ACK_HOST = '127.0.0.1'
    UDP_ACK_PORT = sender_ack_port
    UDP_ACK_ADDR = (UDP_ACK_HOST, UDP_ACK_PORT)

    #To set up a UDP socket for receiving the data
    UDP_recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # UDP_HOST = socket.gethostbyname(socket.gethostname())
    # TODO: change this
    UDP_RECV_HOST = '127.0.0.1'
    # UDP_HOST = socket.gethostbyname(socket.gethostname())
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
    if flagpart == 0:
        ackflag = 0
        finflag = 0
    elif flagpart == 1:
        ackflag = 0
        finflag = 1
    elif flagpart == 16:
        ackflag = 1
        finflag = 0
    elif flagpart == 17:
        ackflag = 1
        finflag = 1
    # TODO: write the first data

    RCV_SEQ_NUM = 0
    while finflag != 1:
        receiveddata = UDP_recv_socket.recvfrom(1024)
        string_size = len(receiveddata[0]) - 20 # for the header
        # TODO:
        received = struct.unpack('!HHIIHHHH%ds' % string_size, receiveddata[0])
        (sender_port, recv_port, seq_num, ack_num, flagpart,
                window_size, checksum, option, datachunk) = received
        if flagpart == 0:
            ackflag = 0
            finflag = 0
        elif flagpart == 1:
            ackflag = 0
            finflag = 1
        elif flagpart == 16:
            ackflag = 1
            finflag = 0
        elif flagpart == 17:
            ackflag = 1
            finflag = 1

        # do the checksum shit
        checksum = True
        # if checksum is good
        ########################
        # PLEASE MAKE SURE TO PROPERLY RENAME THE PORTS
        #######################
        if checksum:
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
                pass

            # else drop the packet
            else:
                pass


        # else if checksum is bad
        else:
            pass