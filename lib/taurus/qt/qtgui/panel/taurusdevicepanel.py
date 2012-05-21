#!/usr/bin/env python

#############################################################################
##
## This file is part of Taurus, a Tango User Interface Library
## 
## http://www.tango-controls.org/static/taurus/latest/doc/html/index.html
##
## Copyright 2011 CELLS / ALBA Synchrotron, Bellaterra, Spain
## 
## Taurus is free software: you can redistribute it and/or modify
## it under the terms of the GNU Lesser General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
## 
## Taurus is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Lesser General Public License for more details.
## 
## You should have received a copy of the GNU Lesser General Public License
## along with Taurus.  If not, see <http://www.gnu.org/licenses/>.
##
#############################################################################

"""
TaurusDevicePanel.py: 
"""

__all__ = ["TaurusDevicePanel","TaurusDevPanel"]

__docformat__ = 'restructuredtext'

import re,traceback,time,sys
from taurus.qt import Qt

import taurus.core
from taurus.qt.qtgui.container import TaurusMainWindow

import taurus.qt.qtgui.resource
                    
from taurus.qt.qtgui.container import TaurusWidget as WIDGET_CLASS
from taurus.qt.qtgui.display import TaurusValueLabel as LABEL_CLASS
from taurus.qt.qtgui.display import TaurusStateLed as LED_CLASS
from taurus.qt.qtgui.panel.taurusvalue import TaurusValue as VALUE_CLASS
from taurus.qt.qtgui.panel.taurusform import TaurusForm as FORM_CLASS
from taurus.qt.qtgui.panel.taurusform import TaurusCommandsForm as COMMAND_CLASS

###############################################################################
# TaurusDevicePanel (from Vacca)

# Variables that control TaurusDevicePanel shape

STATUS_HEIGHT=170
SPLIT_SIZES=[] #[15,50,35]
IMAGE_SIZE=(200,100) #(width,height)

# Helper methods

def matchCl(m,k):
    return re.match(m.lower(),k.lower())

def get_regexp_dict(dct,key,default=None):
    for k,v in dct.items(): #Trying regular expression match
        if matchCl(k,key):
            return v
    for k,v in dct.items(): #If failed, trying if key is contained
        if k.lower() in key.lower():
            return v
    if default is not None: return default
    else: raise Exception('KeyNotFound:%s'%k)
    
def get_eqtype(dev):
    ''' It extracts the eqtype from a device name like domain/family/eqtype-serial'''
    try: eq = str(dev).split('/')[-1].split('-',1)[0].upper()
    except: eq = ''
    return eq
    
def str_to_filter(seq):
    try: f = eval(seq)
    except: f = seq
    if isinstance(f,basestring): return {'.*':[f]}
    elif isinstance(f,list): return {'.*':f}
    else: return f
    taurus.qt.qtgui.resource.getPixmap(':/actions/window-new.svg')
#Stacked palette
def get_White_palette():
        palette = Qt.QPalette()

        brush = Qt.QBrush(Qt.QColor(255,255,255))
        brush.setStyle(Qt.Qt.SolidPattern)
        palette.setBrush(Qt.QPalette.Active,Qt.QPalette.Base,brush)

        brush = Qt.QBrush(Qt.QColor(255,255,255))
        brush.setStyle(Qt.Qt.SolidPattern)
        palette.setBrush(Qt.QPalette.Active,Qt.QPalette.Window,brush)

        brush = Qt.QBrush(Qt.QColor(255,255,255))
        brush.setStyle(Qt.Qt.SolidPattern)
        palette.setBrush(Qt.QPalette.Inactive,Qt.QPalette.Base,brush)

        brush = Qt.QBrush(Qt.QColor(255,255,255))
        brush.setStyle(Qt.Qt.SolidPattern)
        palette.setBrush(Qt.QPalette.Inactive,Qt.QPalette.Window,brush)

        brush = Qt.QBrush(Qt.QColor(255,255,255))
        brush.setStyle(Qt.Qt.SolidPattern)
        palette.setBrush(Qt.QPalette.Disabled,Qt.QPalette.Base,brush)

        brush = Qt.QBrush(Qt.QColor(255,255,255))
        brush.setStyle(Qt.Qt.SolidPattern)
        palette.setBrush(Qt.QPalette.Disabled,Qt.QPalette.Window,brush)
        return palette

# TaurusDevicePanel class

class TaurusDevicePanel(WIDGET_CLASS):
    
    READ_ONLY = False
    _attribute_filter = {} #A dictionary like {device_regexp:[attribute_regexps]}
    _command_filter = {} #A dictionary like {device_regexp:[(command_regexp,default_args)]}
    
    @classmethod
    def setAttributeFilters(klass,filters):
        """ 
        It will set the attribute filters
        filters will be like: {device_regexp:[attribute_regexps]}
        example: {'.*/VGCT-.*': ['ChannelState','p[0-9]']}
        """
        klass._attribute_filter.update(filters)
        
    @classmethod
    def setCommandFilters(klass,filters):
        """ 
        It will set the command filters
        filters will be like: {device_regexp:[command_regexps]}
        example:  {'.*/IPCT-.*': (
                    ('setmode',('SERIAL','LOCAL','STEP','FIXED','START','PROTECT')), 
                    ('onhv1',()), ('offhv1',()), ('onhv2',()), ('offhv2',()), 
                    ('sendcommand',())
                ),}
        """
        klass._command_filter.update(filters)        
    
    def __init__(self,parent=None,model=None,palette=None,bound=True):
        WIDGET_CLASS.__init__(self,parent)
        self.info('In TaurusDevicePanel.__init__()')
        if palette: self.setPalette(palette)
        self.setLayout(Qt.QGridLayout())
        self.bound = bound
        self._dups = []
        self._label = Qt.QLabel()
        self._label.font().setBold(True)
        
        self._stateframe = WIDGET_CLASS(self)
        self._stateframe.setLayout(Qt.QGridLayout())
        self._stateframe.layout().addWidget(Qt.QLabel('State'),0,0,Qt.Qt.AlignCenter)
        self._statelabel = LABEL_CLASS(self._stateframe)
        self._statelabel.setMinimumWidth(100)        
        self._statelabel.setShowQuality(False)
        self._statelabel.setShowState(True)
        self._stateframe.layout().addWidget(self._statelabel,0,1,Qt.Qt.AlignCenter)
        self._state = LED_CLASS(self._stateframe)
        self._state.setShowQuality(False)
        self._stateframe.layout().addWidget(self._state,0,2,Qt.Qt.AlignCenter)        
        
        self._statusframe = Qt.QScrollArea(self)
        self._status = LABEL_CLASS(self._statusframe)
        self._status.setShowQuality(False)
        self._status.setAlignment(Qt.Qt.AlignLeft)
        self._status.setFixedHeight(2000)
        self._status.setFixedWidth(5000)
        #self._statusframe.setFixedHeight(STATUS_HEIGHT)
        self._statusframe.setHorizontalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOn)
        self._statusframe.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOn)
        self._statusframe.setWidget(self._status)
        self._statusframe.setPalette(get_White_palette())
        
        self._attrsframe = Qt.QTabWidget(self)
        
        self._splitter = Qt.QSplitter(Qt.Qt.Vertical,self) ##Horizontal will not allow to show labels of attributes!
        self._splitter.setChildrenCollapsible(False)        
        
        self._attrs,self._comms = None,None
        
        self.layout().addWidget(self._splitter,0,0)
        self._header = Qt.QFrame()
        self._header.setFixedHeight(1.1*IMAGE_SIZE[1])
        self._header.setLayout(Qt.QGridLayout())
        
        self._dup = Qt.QPushButton()
        qpixmap = taurus.qt.qtgui.resource.getPixmap(':/actions/window-new.svg')
        self._dup.setIcon(Qt.QIcon(qpixmap))
        self._dup.setIconSize(Qt.QSize(15,15))
        self.connect(self._dup,Qt.SIGNAL("pressed()"),self.duplicate)
        
        self._image = Qt.QLabel()
            
        self._header.layout().addWidget(self._image,0,0,2,1,Qt.Qt.AlignCenter)
        self._header.layout().addWidget(self._label,0,1,Qt.Qt.AlignLeft)
        self._header.layout().addWidget(self._stateframe,1,1,1,2,Qt.Qt.AlignLeft)
        self._header.layout().addWidget(self._dup,0,2,Qt.Qt.AlignRight)
        
        self._splitter.insertWidget(0,self._header)
        self._splitter.insertWidget(1,self._attrsframe)
        self._splitter.insertWidget(2,self._statusframe)
        self._splitter.setStretchFactor(0,15)
        self._splitter.setStretchFactor(1,65)
        self._splitter.setStretchFactor(2,20)
        
        if model: self.setModel(model)
        
    def duplicate(self):
        self._dups.append(TaurusDevicePanel(bound=False))
        self._dups[-1].setModel(self.model)
        self._dups[-1].show()
    
    @Qt.pyqtSignature("setModel(QString)")
    def setModel(self,model,pixmap=None):
        self.info('In TaurusDevicePanel.setModel(%s)'%model)
        if not model: return None
        model = str(model).split()[0].strip()
        self.debug( 'In TaurusDevicePanel.setModel(%s)'%model)
        if model == self.getModel():
          pass
        else:
            try:
                taurus.Device(model).ping()
                WIDGET_CLASS.setModel(self,model)
                self.setWindowTitle(str(model).upper())
                model = self.getModel()
                self.info('TaurusDevicePanel model set to %s'%model)
                self._label.setText(model.upper())
                font = self._label.font()
                font.setPointSize(15)
                self._label.setFont(font)
                
                iconsize = Qt.QSize(*IMAGE_SIZE)
                if pixmap is not None:
                    #print 'Pixmap is %s'%pixmap
                    qpixmap = Qt.QPixmap(pixmap)
                    if qpixmap.height()>.9*IMAGE_SIZE[1]: qpixmap=qpixmap.scaledToHeight(.9*IMAGE_SIZE[1])
                    if qpixmap.width()>.9*IMAGE_SIZE[0]: qpixmap=qpixmap.scaledToWidth(.9*IMAGE_SIZE[0])
                else:
                    qpixmap = taurus.qt.qtgui.resource.getPixmap(':/logo.png')
                
                self._image.setPixmap(qpixmap)
                
                self._state.setModel(model+'/state')
                if hasattr(self,'_statelabel'): self._statelabel.setModel(model+'/state')
                self._status.setModel(model+'/status')
                try:
                    self._attrsframe.clear()
                    
                    self._attrs = self.get_attrs_form(model,self._attrs,self)
                    if self._attrs: self._attrsframe.addTab(self._attrs,'Attributes')               
                    if not TaurusDevicePanel.READ_ONLY:
                        self._comms = self.get_comms_form(model,self._comms,self)
                        if self._comms: 
                            self._attrsframe.addTab(self._comms,'Commands')
                            self._comms._splitter.setSizes([50,50])
                except:
                    self.warning( traceback.format_exc())
                    qmsg = Qt.QMessageBox(Qt.QMessageBox.Critical,'%s Error'%model,'%s not available'%model,Qt.QMessageBox.Ok,self)
                    qmsg.setDetailedText(traceback.format_exc())
                    qmsg.show()
            except:
                self.debug(traceback.format_exc())
                qmsg = Qt.QMessageBox(Qt.QMessageBox.Critical,'%s Error'%model,'%s not available'%model,Qt.QMessageBox.Ok,self)
                qmsg.show()

        if SPLIT_SIZES: self._splitter.setSizes(SPLIT_SIZES)
        return
        
    def get_attrs_form(self,device,form=None,parent=None):
        filters = get_regexp_dict(TaurusDevicePanel._attribute_filter,get_eqtype(device),['.*'])
        self.debug( 'In TaurusDevicePanel.get_attrs_form(%s,%s)'%(device,filters))
        all = sorted(str(a) for a in taurus.Device(device).get_attribute_list() if str(a).lower() not in ('state','status'))
        attrs = []
        for a in filters:
            for t in all:
                if a and matchCl(a.strip(),t.strip()):
                    aname = '%s/%s' % (device,t)
                    if not aname in attrs:
                        attrs.append(aname)  
        if attrs:
            self.debug( 'Matching attributes are: %s' % str(attrs)[:100])
            if form is None: form = FORM_CLASS(parent)
            elif hasattr(form,'setModel'): form.setModel([])
            ##Configuring the TauForm:
            form.setWithButtons(False)
            form.setWindowTitle(device)
            try: form.setModel(attrs)
            except Exception,e: self.warning('TaurusDevicePanel.ERROR: Unable to setModel for TaurusDevicePanel.attrs_form!!: %s'%traceback.format_exc())
            return form
        else: return None
    
    def get_comms_form(self,device,form=None,parent=None):
        self.debug( 'In TaurusDevicePanel.get_comms_form(%s)'%device)
        params = get_regexp_dict(TaurusDevicePanel._command_filter,get_eqtype(device),[('.*',())])
        if not params: #By default an unknown device type will display no commands
            self.debug('TaurusDevicePanel.get_comms_form(%s): By default an unknown device type will display no commands'% device)
            return None 
        self.info('params: %s'%str(params))
        if not form: 
            form = COMMAND_CLASS(parent)
        elif hasattr(form,'setModel'): 
            form.setModel('')
        try:
            form.setModel(device)
            if params: 
                form.setSortKey(lambda x,vals=[s[0].lower() for s in params]: vals.index(x.cmd_name.lower()) if str(x.cmd_name).lower() in vals else 100)
                form.setViewFilters([lambda c: str(c.cmd_name).lower() not in ('state','status') and any(re.match(s[0].lower(),str(c.cmd_name).lower()) for s in params)])
                form.setDefaultParameters(dict((k,v) for k,v in params if v))
            for wid in form._cmdWidgets:
                if not hasattr(wid,'getCommand') or not hasattr(wid,'setDangerMessage'): continue
                if re.match('.*(on|off|init|open|close).*',str(wid.getCommand().lower())):
                    wid.setDangerMessage('This action may affect other systems!')
            #form._splitter.setStretchFactor(1,70)
            #form._splitter.setStretchFactor(0,30)
            form._splitter.setSizes([50,50])
        except Exception,e: 
            self.warning('Unable to setModel for TaurusDevicePanel.comms_form!!: %s'%traceback.format_exc())
        return form

# Main

def TaurusDevicePanelMain():
    '''A launcher for TaurusDevicePanel.'''
    #!/usr/bin/python
    import sys
    from taurus.qt.qtgui.application import TaurusApplication
    from taurus.core.util import argparse
    
    taurus.setLogLevel(taurus.core.util.Logger.Debug)
    #app = Qt.QApplication(sys.argv)
    #assert len(sys.argv)>1, '\n\nUsage:\n\t> python widgets.py a/device/name [attr_regexp]'
    #model = sys.argv[1]
    #filters = sys.argv[2]
        
    parser = argparse.get_taurus_parser()
    parser.set_usage("%prog [options] devname [attrs]")
    parser.set_description("Taurus Application inspired in Jive and Atk Panel")
    app = TaurusApplication(cmd_line_parser=parser,app_name="TaurusDevicePanel",
                            app_version=taurus.Release.version)
    args = app.get_command_line_args()
    options = app.get_command_line_options()
        
    print 'options: %s'%options
    print 'args: %s'%args
    
    w = TaurusDevicePanel()
    if options.tango_host is None:
        options.tango_host = taurus.Database().getNormalName()
    try: w.setTangoHost(options.tango_host)
    except: pass
    w.setModel(args[0])
    w.setAttributeFilters({args[0]:args[1:]})
    w.show()
    
    sys.exit(app.exec_())             

###############################################################################
# Unused TaurusDevPanel

def filterNonExported(obj):
    if not isinstance(obj,taurus.core.TaurusDevInfo) or obj.exported():
        return obj
    return None

class TaurusDevPanel(TaurusMainWindow):
    '''
    TaurusDevPanel is a Taurus Application inspired in Jive and Atk Panel.
    
    It Provides a Device selector and several dockWidgets for interacting and
    displaying information from the selected device.
    '''
    def __init__(self, parent=None, designMode = False):
        TaurusMainWindow.__init__(self, parent, designMode=designMode)
        
        import taurus.qt.qtgui.ui.ui_TaurusDevPanel
        self._ui = taurus.qt.qtgui.ui.ui_TaurusDevPanel.Ui_TaurusDevPanel()
        self._ui.setupUi(self)
        
        #setting up the device Tree. 
        #@todo: This should be done in the ui file when the TaurusDatabaseTree Designer plugin is available
        import taurus.qt.qtgui.tree
        TaurusDbTreeWidget = taurus.qt.qtgui.tree.TaurusDbTreeWidget

        self.deviceTree = TaurusDbTreeWidget(perspective=taurus.core.TaurusElementType.Device)
        self.deviceTree.getQModel().setSelectables([taurus.core.TaurusElementType.Member])
        #self.deviceTree.insertFilter(filterNonExported)
        self.setCentralWidget(self.deviceTree)        
        
        #needed because of a limitation in when using the useParentModel
        #property from designer and taurus parents are not the same as Qt Parents
        self._ui.taurusAttrForm.recheckTaurusParent()
        self._ui.taurusCommandsForm.recheckTaurusParent()
        
        #Add StateLed to statusBar
#        self.devStateLed = TaurusStateLed()
#        self.statusbar.addPermanentWidget(self.devStateLed)
#        self.devStateLed.setModel('/state')
#        self.devStateLed.setUseParentModel(True)
        
        #register subwidgets for configuration purposes 
        #self.registerConfigDelegate(self.taurusAttrForm)
        #self.registerConfigDelegate(self.deviceTree)
        self.registerConfigDelegate(self._ui.taurusCommandsForm)
        
        self.loadSettings()
        self.createActions()
        
        #self.addToolBar(self.basicTaurusToolbar())
        
        self.connect(self.deviceTree, Qt.SIGNAL("currentItemChanged"),self.onItemSelectionChanged)
                
        self.updatePerspectivesMenu()
        if not designMode:
            self.splashScreen().finish(self)
    
    def createActions(self):
        '''create actions '''
        #View Menu
        self.showAttrAction = self.viewMenu.addAction(self._ui.attrDW.toggleViewAction())
        self.showCommandsAction = self.viewMenu.addAction(self._ui.commandsDW.toggleViewAction())
        self.showTrendAction = self.viewMenu.addAction(self._ui.trendDW.toggleViewAction())
        
    def setTangoHost(self, host):
        '''extended from :class:setTangoHost'''
        TaurusMainWindow.setTangoHost(self, host)
        self.deviceTree.setModel(host)
        #self.deviceTree.insertFilter(filterNonExported)
        
    def onItemSelectionChanged(self, current, previous):
        itemData = current.itemData()
        if isinstance(itemData, taurus.core.TaurusDevInfo):
            self.onDeviceSelected(itemData)
        
    def onDeviceSelected(self, devinfo):
        devname = devinfo.name()
        msg = 'Connecting to "%s"...'%devname
        self.statusBar().showMessage(msg)
        #abort if the device is not exported
        if not devinfo.exported():
            msg = 'Connection to "%s" failed (not exported)'%devname
            self.statusBar().showMessage(msg)
            self.info(msg)
            Qt.QMessageBox.warning(self, "Device unreachable", msg)
            self.setModel('')
            return
        self.setDevice(devname)
        
    def setDevice(self,devname):
        #try to connect with the device
        self.setModel(devname)
        dev = self.getModelObj()
        dev.state()
        state = dev.getSWState()
        #test the connection
        if state == taurus.core.TaurusSWDevState.Running:
            msg = 'Connected to "%s"'%devname
            self.statusBar().showMessage(msg)
            self._ui.attrDW.setWindowTitle('Attributes - %s'%devname)
            self._ui.commandsDW.setWindowTitle('Commands - %s'%devname)
        else:
            #reset the model if the connection failed
            msg = 'Connection to "%s" failed (state = %s)'%(devname, taurus.core.TaurusSWDevState.whatis(state))
            self.statusBar().showMessage(msg)
            self.info(msg)
            Qt.QMessageBox.warning(self, "Device unreachable", msg)
            self.setModel('')
            
    @classmethod
    def getQtDesignerPluginInfo(cls):
        ret = TaurusMainWindow.getQtDesignerPluginInfo()
        ret['module'] = 'taurus.qt.qtgui.panel'
        return ret

###############################################################################
# Unused Main
    
#def TaurusPanelMain():
    #'''A launcher for TaurusPanel.'''
    ### NOTE: DON'T PUT TEST CODE HERE.
    ### THIS IS CALLED FROM THE LAUNCHER SCRIPT (<taurus>/scripts/tauruspanel)
    #from taurus.qt.qtgui.application import TaurusApplication
    #from taurus.core.util import argparse
    #import sys
    
    #parser = argparse.get_taurus_parser()
    #parser.set_usage("%prog [options] [devname]")
    #parser.set_description("Taurus Application inspired in Jive and Atk Panel")
    #app = TaurusApplication(cmd_line_parser=parser,app_name="tauruspanel",
                            #app_version=taurus.Release.version)
    #args = app.get_command_line_args()
    #options = app.get_command_line_options()
    
    #w = TaurusDevPanel()
    
    #if options.tango_host is None:
        #options.tango_host = taurus.Database().getNormalName()
    #w.setTangoHost(options.tango_host)
    #if len(args) == 1: 
        #w.setDevice(args[0])
    
    #w.show()
    
    #sys.exit(app.exec_()) 

###############################################################################
    
if __name__ == "__main__":
    TaurusDevicePanelMain() 