import sys
import socket
import thread
from threading import Thread
from datetime import datetime
from time import strftime
import struct

def make_header(source_port, dest_port, seq_num, ack_num, ACK_flag, FIN_flag, window_size, checksum, datachunk):
    "To pack the reliable file transfer data with TCP-like header"

    if ACK_flag == 0 and FIN_flag == 0:
        flagpart = 0
    elif ACK_flag == 0 and FIN_flag == 1:
        flagpart = 1
    elif ACK_flag == 1 and FIN_flag == 0:
        flagpart = 16
    elif ACK_flag == 1 and FIN_flag == 1:
        flagpart = 17

    option = 0
    header = struct.pack('!HHIIHHHH%ds' % len(datachunk), source_port, dest_port,
            seq_num, ack_num, flagpart, window_size, checksum, option, datachunk)

    return header

def write_logfile(log_filename, timestamp, source, destination, seq_num, ack_num, ack_flag, fin_flag):
    "To write log file after each sending"

    logline = str(timestamp).ljust(25) + source.ljust(20) + destination.ljust(20) + str(seq_num).ljust(10) + \
              str(ack_num).ljust(10) + str(ack_flag).ljust(10) + str(fin_flag).ljust(10) + '\n'

    if log_filename == 'stdout':
        print logline
    else:
        try:
            with open(log_filename, "a") as f:
                f.write(logline)
        except:
            print 'Logfile I/O error'

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

    total = 0
    for num in range(len(new_packet)):
        total += ord(new_packet[num]) << 8 if num % 2 == 0 else ord(new_packet[num])
    return total % 65536

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
    if(len(sys.argv) != 6):
        print 'Usage:'
        print 'python receiver.py <filename> <listening_port> <sender_IP> <sender_ack_port> <log_filename>'
        sys.exit()
    filename = sys.argv[1]
    try:
        listening_port = int(sys.argv[2])
    except ValueError:
        print '<listening_port> is an integer.'
        sys.exit()
    try:
        sender_IP = socket.gethostbyname(sys.argv[3])
    except:
        print 'sender_IP error'
        sys.exit(1)

    try:
        sender_ack_port = int(sys.argv[4])
    except ValueError:
        print '<sender_ack_port> is an integer'
        sys.exit()
    log_filename = sys.argv[5]
    # write label line to logfile
    write_logfile(log_filename, 'timestamp', 'source', 'destination', 'seq_num', 'ack_num', 'ack_flag', 'fin_flag')

    # set up a UDP socket for sending ACKs
    UDP_ack_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    UDP_ACK_HOST = sender_IP
    UDP_ACK_PORT = sender_ack_port
    UDP_ACK_ADDR = (UDP_ACK_HOST, UDP_ACK_PORT)

    #To set up a UDP socket for receiving the data
    UDP_recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    UDP_RECV_HOST = socket.gethostbyname(socket.gethostname())
    UDP_RECV_PORT = listening_port
    UDP_RECV_ADDR = (UDP_RECV_HOST, UDP_RECV_PORT)

    try:
        UDP_recv_socket.bind(UDP_RECV_ADDR)
    except socket.error, msg:
        print 'Failed to bind socket. Error code ['+str(msg[0])+'] Error message:'+msg[1]
        sys.exit()

    #Receive first data and check the packet
    receiveddata = UDP_recv_socket.recvfrom(1024)
    string_size = len(receiveddata[0]) - 20 # for the header
    received = struct.unpack('!HHIIHHHH%ds' % string_size, receiveddata[0])
    (sender_port, recv_port, seq_num, ack_num, flagpart,
            window_size, checksum, option, datachunk) = received
    ackflag, finflag = getflags(flagpart)
    if checksum_verify(receiveddata[0]):
        ACK_FLAG = 1
        FIN_FLAG = 0
        rft_checksum = 0
        packet = ''
        sendpacket = make_header(recv_port, sender_port, seq_num,
            seq_num, ACK_FLAG, FIN_FLAG, window_size, rft_checksum, packet)

        # log the packet just received
        timestamp = datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
        source = sender_IP
        destination = socket.gethostbyname(socket.gethostname())
        write_logfile(log_filename, timestamp, source, destination, seq_num, ack_num, ackflag, finflag)
        # write the data to the file
        with open(filename, 'a') as f:
            f.write(datachunk)

        # send the ACK
        try:
            UDP_ack_socket.sendto(sendpacket, UDP_ACK_ADDR)
        except socket.error, msg:
            print 'socket error code ['+str(msg[0])+'], error message: '+str(msg[1])
            sys.exit()
        # log the ACK just sent
        timestamp = datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
        source = socket.gethostbyname(socket.gethostname())
        destination = sender_IP
        write_logfile(log_filename, timestamp, source, destination, seq_num, seq_num, ackflag, finflag)

    RCV_SEQ_NUM = 0
    while finflag != 1:
        receiveddata = UDP_recv_socket.recvfrom(1024)
        string_size = len(receiveddata[0]) - 20 # for the header
        received = struct.unpack('!HHIIHHHH%ds' % string_size, receiveddata[0])
        (sender_port, recv_port, seq_num, ack_num, flagpart,
                window_size, checksum, option, datachunk) = received
        ackflag, finflag = getflags(flagpart)
        # if checksum is good
        if checksum_verify(receiveddata[0]):
            # check the sequence number
            if seq_num == RCV_SEQ_NUM:
                ACK_FLAG = 1
                FIN_FLAG = 0
                rft_checksum = 0
                RCV_SEQ_NUM += 1
                packet = ''
                sendpacket = make_header(recv_port, sender_port, RCV_SEQ_NUM,
                    seq_num, ACK_FLAG, FIN_FLAG, window_size, rft_checksum, packet)

                # log the packet just received
                timestamp = datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
                source = sender_IP
                destination = socket.gethostbyname(socket.gethostname())
                write_logfile(log_filename, timestamp, source, destination, seq_num, ack_num, ackflag, finflag)
                # write the data to the file
                with open(filename, 'a') as f:
                    f.write(datachunk)

                # send the ACK
                try:
                    UDP_ack_socket.sendto(sendpacket, UDP_ACK_ADDR)
                except socket.error, msg:
                    print 'socket error code ['+str(msg[0])+'], error message: '+str(msg[1])
                    sys.exit()
                # log the ACK just sent
                timestamp = datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
                source = socket.gethostbyname(socket.gethostname())
                destination = sender_IP
                write_logfile(log_filename, timestamp, source, destination, RCV_SEQ_NUM, seq_num, ackflag, finflag)

            # if its a lower seq num than expected, just ACK
            elif seq_num < RCV_SEQ_NUM:
                ACK_FLAG = 1
                FIN_FLAG = 0
                rft_checksum = 0
                packet = ''
                sendpacket = make_header(recv_port, sender_port, seq_num,
                    seq_num, ACK_FLAG, FIN_FLAG, window_size, rft_checksum, packet)

                # send the ACK
                try:
                    UDP_ack_socket.sendto(sendpacket, UDP_ACK_ADDR)
                except socket.error, msg:
                    print 'socket error code ['+str(msg[0])+'], error message: '+str(msg[1])
                    sys.exit()

                # log the ACK just sent
                timestamp = datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
                source = socket.gethostbyname(socket.gethostname())
                destination = sender_IP
                write_logfile(log_filename, timestamp, source, destination, RCV_SEQ_NUM, seq_num, ackflag, finflag)

            else:
                pass

        # else if checksum is bad
        else:
            ACK_FLAG = 0
            FIN_FLAG = 0
            rft_checksum = 0
            packet = ''
            sendpacket = make_header(recv_port, sender_port, RCV_SEQ_NUM,
                seq_num, ACK_FLAG, FIN_FLAG, window_size, rft_checksum, packet)
            try:
                UDP_ack_socket.sendto(sendpacket, UDP_ACK_ADDR)
            except socket.error, msg:
                print 'socket error code ['+str(msg[0])+'], error message: '+str(msg[1])
                sys.exit()

    print 'Delivery completed successfully'
