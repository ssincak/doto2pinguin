#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2016 Stefan Sincak. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import platform
import subprocess
import re
import threading
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from functools import partial

class DotoServer(object):
    """ Info about Doto 2 server """

    def __init__(self, name, address):
        self.name = name
        self.address = address

# IP list from: https://steamcommunity.com/sharedfiles/filedetails/?id=217075877
DOTO_SERVERS = [DotoServer("EU East 1", "vie.valve.net"),
                DotoServer("EU East 2", "185.25.182.1"),
                DotoServer("EU West 1", "lux.valve.net"),
                DotoServer("EU West 2", "146.66.158.1"),
                DotoServer("Russia 1", "sto.valve.net"),
                DotoServer("Russia 2", "185.25.180.1 "),
                DotoServer("US East", "iad.valve.net"),
                DotoServer("US West", "eat.valve.net"),
                DotoServer("SE Asia 1", "sgp-1.valve.net"),
                DotoServer("SE Asia 2", "sgp-2.valve.net"),
                DotoServer("South America 1", "gru.valve.net"),
                DotoServer("South America 2", "209.197.25.1"),
                DotoServer("South America 3", "209.197.29.1"),
                DotoServer("South Africa 1", "cpt-1.valve.net"),
                DotoServer("South Africa 2", "197.80.200.1"),
                DotoServer("South Africa 3", "197.84.209.1"),
                DotoServer("South Africa 4", "196.38.180.1 "),
                DotoServer("Peru", "191.98.144.1"),
                DotoServer("India", "116.202.224.146"),
                DotoServer("Australia", "syd.valve.net"),
                DotoServer("Dubai", "dxb.valve.net")
           ];
               
class PingThread(threading.Thread):
    """ Runs 'ping' command in the background.
        When the thread finishes, ping value or
        packet loss is parsed from stdout.

        Attributes:
            time: ping in ms, -1 when packet was lost
    """

    def __init__(self, hostname, timeout):
        """ Initializes pinging thread with host address and timeout (in ms) """
        self._stdout = None
        self._stderr = None
        self._hostname = hostname
        self._timeout = timeout
        self.time = 0
        threading.Thread.__init__(self)

    def run(self):
        isWindows = platform.system() == "Windows"
        
        if isWindows:
            command="ping "+self._hostname+" -n 1 -w "+str(self._timeout)
        else:
            command="ping -i "+str(self._timeout/1000)+" -c 1 " + self._hostname

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
        p = subprocess.Popen(command, startupinfo=startupinfo, stdout=subprocess.PIPE)
        
        self._stdout, self._stderr = p.communicate()

        matches=re.match('.*time=([0-9]+)ms.*', self._stdout, re.DOTALL)
        if matches:
            self.time = int(matches.group(1))
        else: 
            self.time = -1;  # ping could not be parsed (packet lost)

class PingStatistics(object):
    """ Holds ping values in a list
        and computes minimum, maximum and
        average values.

        Attributes:
            min: minimum ping
            max: maximum ping
            avg: average ping
            lossCount: number of lost packets
            lossPercent: percent of lost packets in all packets
    """

    def __init__(self):
        self.min = 0
        self.max = 0
        self.avg = 0
        self.lossCount = 0
        self.lossPercent = 0
        self._pings = []
        
    def update(self, ping):
        if len(self._pings) > 0:
            if ping >= 0:
                self.min = min(self.min, ping)
                self.max = max(self.max, ping)
                self.avg = sum(self._pings) / len(self._pings)
        else:
            self.min = ping
            self.max = ping
            self.avg = ping

        if ping >= 0:
            self._pings.append(ping)
        else:
            self.lossCount += 1

        # loss percent = lossCount / totalPings
        if len(self._pings) > 0 or self.lossCount > 0:
            self.lossPercent = int((float(self.lossCount) /
                                    float(len(self._pings)+self.lossCount))*100.0)
            
        
class QServerState(QWidget):
    """ Widget that displays ping stats
        for one specified Doto server.

        Each time interval a ping is read
        from PingThread. The PingStatistics are
        then updated with that ping value and
        the widget is redrawn.
    """

    interval = 1000
    pingTimeout = 4000
    maxPing = 200
    goodColor = QColor(0, 255, 0)
    badColor = QColor(255, 0, 0)
    infoHeight = 30
    barWidth = 10
    barOffset = 10
    
    def __init__(self, parent, serverInfo):
        super(QServerState, self).__init__(parent);

        self.show()
        self.parentWidget().mainLayout.addWidget(self);

        self._serverInfo = serverInfo;
        self._pingStats = PingStatistics();

        self._graphPings = [];

        self.startPingThread();

        self._timer = QTimer()
        self._timer.timeout.connect(self.refresh);
        self._timer.timeout.connect(self.update);
        self._timer.start(self.interval)

    def paintEvent(self, event):
        self.redraw(event);

    def getPingColor(self, ping):
        fac = float(min(ping, self.maxPing)) / float(self.maxPing);
        invFac = 1.0 - fac;
        
        return QColor(invFac*self.goodColor.red() + fac*self.badColor.red(),
                      invFac*self.goodColor.green() + fac*self.badColor.green(),
                      invFac*self.goodColor.blue() + fac*self.badColor.blue());

    def getStatsText(self):
        return "ping min/max/avg : %d/%d/%d" % (self._pingStats.min, self._pingStats.max, self._pingStats.avg);
        
    def redraw(self, event):
        br = event.rect()
        tr = QRect(br.left(), br.top(), br.width(), self.infoHeight);
        gr = QRect(br.left(), br.top() + self.infoHeight, br.width(), br.height()-self.infoHeight);
        
        top = gr.top()
        bottom = gr.bottom()
        width = gr.width()
        height = gr.height()
        
        qp = QPainter()
        qp.begin(self)
        qp.eraseRect(event.rect());
        
        # info area
        qp.setPen(QColor(0, 0, 0))
        qp.setFont(QFont('Decorative', 10))

        qp.drawText(tr, Qt.AlignLeft | Qt.AlignVCenter, "{} ({})".format(self._serverInfo.name, self._serverInfo.address))
        qp.drawText(tr, Qt.AlignRight | Qt.AlignVCenter, self.getStatsText())

        qp.setPen(QColor(0, 0, 0) if self._pingStats.lossCount == 0 else QColor(255, 0, 0))
        qp.drawText(tr, Qt.AlignCenter, "loss count/percent: %d/%d%%" % (self._pingStats.lossCount, self._pingStats.lossPercent));

        qp.setPen(QColor(168, 34, 3))
        qp.drawText(gr, Qt.AlignLeft | Qt.AlignBottom, "0")
        qp.drawText(gr, Qt.AlignLeft | Qt.AlignVCenter, str(self.maxPing/2))
        qp.drawText(QRect(gr.left(), gr.top() + gr.height()*0.75 - 10, gr.width(), gr.height()/4), Qt.AlignLeft, str(self.maxPing/4))
        qp.drawText(gr, Qt.AlignLeft, str(self.maxPing))

        # graph segments
        i = 0;
        for seg in self._graphPings:
            p = min(int(seg), self.maxPing);
            fac = float(p) / float(self.maxPing);
            x = self.barOffset + (i+1) * self.barWidth;
            
            if p < 0:  # loss
                qp.setBrush(QBrush(QColor(255,0,0), Qt.BDiagPattern))
                qp.drawRect(x, top, self.barWidth, bottom)
            else:  # valid ping
                qp.setBrush(self.getPingColor(p))
                qp.drawRect(x, bottom - height*fac, self.barWidth, height*fac)
                
            i += 1

        # graph lines
        linePen = QPen(Qt.black, 1, Qt.SolidLine)
        linePen.setStyle(Qt.SolidLine)
        qp.setPen(linePen)

        qp.drawLine(20, top, width, top)
        linePen.setStyle(Qt.DashDotDotLine)
        qp.setPen(linePen)
        qp.drawLine(20, top + (height/2), width, top + (height/2))
        qp.drawLine(20, top + (height*0.75), width, top + (height*0.75))
        linePen.setStyle(Qt.SolidLine)
        qp.setPen(linePen)
        qp.drawLine(20, bottom, width, bottom)
        
        qp.end()

    def stop(self):
        self._timer.stop();
        self.pingThread.join();

    def resume(self):
        self._timer.start();
        self.startPingThread();
        
    def remove(self):
        self.stop();
        self.setParent(None);

    def maxGraphPings(self):
        return (self.parentWidget().mainLayout.geometry().width() -
                self.barOffset - self.barWidth*2) / self.barWidth;

    def startPingThread(self):
        self.pingThread = PingThread(self._serverInfo.address, self.pingTimeout);
        self.pingThread.start();
        
    @pyqtSlot()
    def refresh(self):
        if self.pingThread.isAlive():
            # ping thread is still alive (no ping or timeout yet),
            # ping is probably higher than our timer interval
            # we'll just wait till it finishes and check on next refresh
            return;
        
        # read ping and update stats
        self.pingThread.join();
        curPing = self.pingThread.time;
        self._pingStats.update(curPing);

        # erase current screen graph when our last segment position is out of window
        if len(self._graphPings) >= self.maxGraphPings():
            self._graphPings = []
            
        self._graphPings.append(curPing);
        
        self.startPingThread();

class DotoPinguin(QWidget):
    """ Main Widget of Doto Pinguin. """

    defaultSize = (640, 200)
    displayedServerHeight = 200
    maxServersOnScreen = 2
    displayedServers = dict()
    serversPaused = False
    
    def checkboxStateChange(self, checkbox, serverIdx):
        if serverIdx in self.displayedServers:
            self.displayedServers[serverIdx].remove()
            self.displayedServers.pop(serverIdx, None)
            self.stopButton.hide();
            self.horizLine.hide();
        else:
            self.displayedServers[serverIdx] = QServerState(self, DOTO_SERVERS[serverIdx])
            self.stopButton.show()
            self.horizLine.show()

        self.resize(self.defaultSize[0], self.defaultSize[1] +
                    self.displayedServerHeight*min(self.maxServersOnScreen, len(self.displayedServers)))

    def stopUpdate(self):
        for key,server in self.displayedServers.iteritems():
            if self.serversPaused:
                server.resume()
                self.stopButton.setText("Stop")
                self.serversPaused = False
            else:
                server.stop()
                self.stopButton.setText("Resume")
                self.serversPaused = True
        
    def __init__(self, parent = None):
        super(DotoPinguin, self).__init__(parent)
      
        self.mainLayout = QVBoxLayout()
        
        # server checkboxes
        layout = QGridLayout()
        i = 0
        for ds in DOTO_SERVERS:
            checkBox = QCheckBox(ds.name)
            checked_slot = partial(self.checkboxStateChange, checkBox, i)
            checkBox.stateChanged.connect(checked_slot)
            layout.addWidget(checkBox, i/3, i%3)
            i += 1

        self.mainLayout.addLayout(layout)

        # horizontal separator under checkboxes
        self.horizLine = QFrame()
        self.horizLine.setFrameStyle(QFrame.HLine)
        self.horizLine.setGeometry(QRect(0, 0, self.frameGeometry().width(), 1))
        self.horizLine.hide()
        self.mainLayout.addWidget(self.horizLine)

        # button for pausing ping update
        self.stopButton = QPushButton("Pause", self)
        self.stopButton.clicked.connect(self.stopUpdate)
        self.stopButton.hide()
        self.mainLayout.addWidget(self.stopButton)
        
        self.resize(self.defaultSize[0], self.defaultSize[1])
        self.setLayout(self.mainLayout)
        self.setWindowTitle("Doto 2 Pinguin")
        
def main():
   app = QApplication(sys.argv)
   c = DotoPinguin()
   c.show()
   sys.exit(app.exec_())

if __name__ == '__main__':
   main()
