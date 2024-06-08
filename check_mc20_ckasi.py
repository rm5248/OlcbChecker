#!/usr/bin/env python3.10
'''
This uses a CAN link layer to check memmory address space information interaction

Usage:
python3.10 check_mc20_ckasi.py

The -h option will display a full list of options.
'''

import sys

from openlcb.nodeid import NodeID
from openlcb.message import Message
from openlcb.mti import MTI
from openlcb.pip import PIP

from queue import Empty

import olcbchecker.setup

def getReplyDatagram(destination) :
    '''
    Invoked after a datagram has been sent, this waits
    for first the datagram reply message, then a 
    datagram message that contains a reply.  It 
    replies with a datagram OK, then returns the reply datagram message.
    Raises Exception if something went wrong.
    '''
    # first, wait for the reply
    while True :
        try :
            received = olcbchecker.getMessage() # timeout if no entries
            # is this a datagram reply, OK or not?
            if not (received.mti == MTI.Datagram_Received_OK or received.mti == MTI.Datagram_Rejected) : 
                continue # wait for next
    
            if destination != received.source : # check source in message header
                continue
    
            if NodeID(olcbchecker.ownnodeid()) != received.destination : # check destination in message header
                continue
    
            if received.mti == MTI.Datagram_Received_OK :
                # OK, proceed
                break
            else : # must be datagram rejected
                # can't proceed
                raise Exception("Failure - Original Datagram rejected")

        except Empty:
            raise Exception("Failure - no reply to original request")
    
    # now wait for the reply datagram
    while True :
        try :
            received = olcbchecker.getMessage() # timeout if no entries
            # is this a datagram reply, OK or not?
            if not (received.mti == MTI.Datagram) : 
                continue # wait for next
    
            if destination != received.source : # check source in message header
                continue
    
            if NodeID(olcbchecker.ownnodeid()) != received.destination : # check destination in message header
                continue

            # here we've received the reply datagram
            # send the reply
            message = Message(MTI.Datagram_Received_OK, NodeID(olcbchecker.ownnodeid()), destination, [0])
            olcbchecker.sendMessage(message)

            return received
            
        except Empty:
            raise Exception("Failure - no reply datagram received")
    


def check():
    # set up the infrastructure

    trace = olcbchecker.trace() # just to be shorter

    # pull any early received messages
    olcbchecker.purgeMessages()

    # get configured DUT node ID - this uses Verify Global in some cases, but not all
    destination = olcbchecker.getTargetID()

    ###############################
    # checking sequence starts here
    ###############################
    
    # check if PIP says this is present
    pipSet = olcbchecker.gatherPIP(destination)  # needed for CDI check later
    if olcbchecker.isCheckPip() : 
        if pipSet is None:
            print ("Failed in setup, no PIP information received")
            return (2)
        if not PIP.MEMORY_CONFIGURATION_PROTOCOL in pipSet :
            if trace >= 10 : 
                print("Passed - due to Memory Configuration protocol not in PIP")
            return(0)

    # For each of these spaces, will sent a "Get Address Space Information Command" and check reply
    spaces = [0xFD] # space required by memory _configuration_ standard
    # add CDI if not checking PIP or not present
    if pipSet == None or PIP.CONFIGURATION_DESCRIPTION_INFORMATION in pipSet :
        spaces.append(0xFF)

    for space in spaces: 

        # send a "Get Address Space Information Command" datagram to provoke response
        message = Message(MTI.Datagram, NodeID(olcbchecker.ownnodeid()), destination, [0x20, 0x84, space])
        olcbchecker.sendMessage(message)

        try :
            reply = getReplyDatagram(destination)
        except Exception as e:
            print (e)
            return (3)
        
        if len(reply.data) < 8 and len(reply.data) > 2 :
            print ("Failure: space 0x{:02X} reply was too short: {}; byte[1] = 0x{:02X}".format(space, len(reply.data), reply.data[1]))
            return (3)
        elif len(reply.data) < 8 :
            print ("Failure: space 0x{:02X} reply was too short: {}".format(space, len(reply.data)) )
            return (3)
        
        # check that the reply says the space is present
        if reply.data[1] != 0x87 :
            print ("Warning - Space 0x{:02X} reply was 0x{:02x}, not 'address space present 0x87': {}"
                    .format(space, reply.data[1], reply.data))

        if reply.data[2] != space :
            print (("Failure: space 0x{:02X} address space number didn't match").format(space))
            return (3)
              
        if (reply.data[7]&0xFE) != 0 :
            print (("Failure: space 0x{:02X} improper flag bits set").format(space))
            return (3)
    
        if (reply.data[7]*0x01) != 0 :
            # check that low address is present
            if len(reply.data) < 12 :
                print (("Failure: space 0x{:02X} flagged containing low address but not present").format(space))
                return (3)
                
    if trace >= 10 : print("Passed")
    return 0

if __name__ == "__main__":
    sys.exit(check())
