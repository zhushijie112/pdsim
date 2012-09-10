import sys
sys.path.append('..')

import pdsim_plugins
import pdsim_panels
from PDSim.flow.flow import FlowPath
from PDSim.core.core import Tube
from PDSim.core.containers import ControlVolume
from PDSim.scroll import scroll_geo
from math import pi
import wx
from PDSim.scroll.plots import plotScrollSet

LabeledItem = pdsim_panels.LabeledItem

class struct(object):
    pass

class InjectionViewerDialog(wx.Dialog):
    """
    A simple dialog with plot of the locations of the injection ports overlaid
    on the scroll wraps to allow easy visualization of the port locations
    """
    def __init__(self, theta, geo):
        """
        Parameters
        ----------
        theta : float
            crank angle in the range [0, :math:`2\pi`] 
        geo : geoVals instance
        """
        wx.Dialog.__init__(self, parent = None)
        
        #: Make class variable since needed by add_port
        self.theta = theta
        #: Make class variable since needed by add_port
        self.geo = geo
        
        #: A matplotlib panel with a figure inside
        self.PP = pdsim_panels.PlotPanel(self)
        #: The axis that the plot will go in
        self.ax = self.PP.figure.add_axes((0,0,1,1))
        
        #A blank scroll wrap
        plotScrollSet(theta, 
                      geo, 
                      axis = self.ax, 
                      use_offset = geo.phi_ie_offset>0)
        
        #: The sizer for the panel 
        sizer = wx.BoxSizer(wx.VERTICAL)
        #Add the plot to it
        sizer.Add(self.PP)
        #Layout the sizer
        sizer.Layout()
        #Fit the dialog to its contents
        self.Fit()
        
    def add_port(self, phi, inner_outer):
        """
        Add an injection port to the axis given by the scroll set plot
        
        Parameters
        ----------
        phi : float
            involute angle of injection port
        inner_outer : string
            If ``'i'``, phi is along the inner involute of the fixed scroll
            
            If ``'o'``, phi is along the outer involute of the fixed scroll
        
        """
        scroll_geo.plot_injection_ports(self.theta, self.geo, phi, self.ax, inner_outer)
        
class InjectionPortPanel(wx.Panel):
    """
    A panel with the values for one injection port
    """
    def __init__(self, parent, index):
        wx.Panel.__init__(self,parent)
        
        #: The index of the panel
        self.index = index
        
        #: A textual string with the 
        self.indexText = wx.StaticText(self,label='#'+str(index))
        
        self.AddPort = wx.Button(self, label='+',style = wx.ID_REMOVE)
        self.RemovePort = wx.Button(self,label='-',style = wx.ID_REMOVE)
        self.AddPort.Bind(wx.EVT_BUTTON,lambda(event):self.Parent.OnAddPort(self))
        self.RemovePort.Bind(wx.EVT_BUTTON,lambda(event):self.Parent.OnRemovePort(self))
        
        button_sizer = wx.BoxSizer(wx.VERTICAL)
        button_sizer.Add(self.indexText,0,wx.EXPAND| wx.ALIGN_CENTER)
        button_sizer.Add(self.AddPort,0,wx.EXPAND| wx.ALIGN_CENTER)
        button_sizer.Add(self.RemovePort,0,wx.EXPAND| wx.ALIGN_CENTER)
        
        element_sizer = wx.FlexGridSizer(cols=2,hgap = 2, vgap = 2)
        element_sizer.AddSpacer(10)
        element_sizer.AddSpacer(10)
        element_sizer.Add(wx.StaticText(self,label="Involute Angle"))
        self.phi_inj_port = wx.TextCtrl(self,value="7.141") 
        self.phi_inj_port.SetToolTipString('If you want symmetric injection ports, the involute angle on the inner involute should be pi radians greater than that on the outer involute.  View the ports to be sure')
        element_sizer.Add(self.phi_inj_port)
        element_sizer.Add(wx.StaticText(self,label="Neighbor Involute"))
        self.involute = wx.ComboBox(self)
        self.involute.AppendItems(['Outer involute','Inner involute'])
        self.involute.SetSelection(0)
        self.involute.SetEditable(False)
        element_sizer.Add(self.involute)
        element_sizer.Add(wx.StaticText(self,label="Uses check valve"))
        self.check_valve = wx.CheckBox(self,label="")
        element_sizer.Add(self.check_valve)
        self.SymmLabel = wx.StaticText(self,label='Symmetric with #')
        self.SymmTarget = wx.ComboBox(self)
        self.SymmTarget.Append('None')
        self.SymmTarget.SetSelection(0)
        self.SymmTarget.SetEditable(False)
        element_sizer.Add(self.SymmLabel)
        element_sizer.Add(self.SymmTarget)
        self.SymmTarget.Bind(wx.EVT_COMBOBOX, self.OnMakeSymmetric)
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(button_sizer,1,wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(element_sizer)
        self.SetSizer(sizer)
        sizer.Layout()
        
        self.set_index(index)
        
    def set_index(self, index):
        """
        A convenience function for setting the index for the port and 
        doing any further work required in the GUI
        
        Parameters
        ----------
        index : int
            The 1-based index of the port
        """
        self.index = index
        self.indexText.SetLabel('#'+str(index))
        
    def set_values(self,phi,inner_outer,check_valve,symmetric):
        """
        Takes in a tuple of involute_angle, inner_outer, and check_valve and
        sets the values in the panel
        
        Parameters
        ----------
        phi : float
        inner_outer : string
            If ``'i'``, phi is along the inner involute of the fixed scroll
            
            If ``'o'``, phi is along the outer involute of the fixed scroll
        check_valve : string
            If lower-case value is ``true``, check valves are being used for this port
        symmetric : string
            If 'None', no symmetric link for this port, otherwise it is the string
            representation of an integer with the 1-based index of the port
        """
        self.phi_inj_port.SetValue(str(phi))
        self.check_valve.SetValue(check_valve.lower()=='true')
        if inner_outer == 'i':
            self.involute.SetValue('Inner involute')
        elif inner_outer == 'o':
            self.involute.SetValue('Outer involute')
        else:
            raise ValueError
        self.SymmTarget.SetStringSelection(symmetric)
        if not symmetric == 'None':
            self.OnMakeSymmetric() 
    
    def get_values(self):
        """
        Returns a tuple of phi, inner_outer, check_valve
        
        Variables as described as in set_values(), but check_valve is a boolean here
        """
        if self.involute.GetStringSelection() == 'Outer involute':
            inner_outer = 'o'
        elif self.involute.GetStringSelection() == 'Inner involute':
            inner_outer = 'i'
        else:
            raise ValueError
        
        return float(self.phi_inj_port.GetValue()), inner_outer, self.check_valve.IsChecked()
    
    def OnMakeSymmetric(self, event = None):
        """
        An event handler for changing the symmetric nature of the 
        """
        # Skip the event so that other objects also running the same handler can
        # do so for instance if there are multiple ports that are symmetric with
        # the port
        if event is not None:
            event.Skip()
        #Get the index if possible 
        I = None   
        try:
            I = int(self.SymmTarget.GetStringSelection())
        except ValueError:
            pass
        
        #If symmetric linking is enabled, 
        if I is not None:
            #Get the symmetric port and its involute angle
            port = self.Parent.ports_list[I-1]
            phi = float(port.phi_inj_port.GetValue())
            if port.involute.GetStringSelection() == 'Inner involute':
                self.involute.SetStringSelection('Outer involute')
                self.phi_inj_port.SetValue(str(phi-pi))
            if port.involute.GetStringSelection() == 'Outer involute':
                self.involute.SetStringSelection('Inner involute')
                self.phi_inj_port.SetValue(str(phi+pi))
            self.involute.Enable(False)
            self.phi_inj_port.Enable(False)
            port.SymmTarget.Enable(False)
            
            #If this port instance fired the event (ie not from the symmetric port)
            #bind the events to the symmetric object
            if event is None or event.GetEventObject().Parent == self:
                port.involute.Bind(wx.EVT_COMBOBOX, self.OnMakeSymmetric)
                port.phi_inj_port.Bind(wx.EVT_TEXT, self.OnMakeSymmetric)
        else:
            self.involute.Enable(True)
            self.phi_inj_port.Enable(True)
        
class InjectionElementPanel(wx.Panel):
    """
    A panel with the injection values for one injection line with a box around it
    """
    def __init__(self, parent,index):
        wx.Panel.__init__(self,parent)
        
        #Inputs Toolbook
        ITB = self.GetTopLevelParent().MTB.InputsTB
        Fluid = None
        for panel in ITB.panels:
            if panel.Name == 'StatePanel':
                Fluid = panel.SuctionState.GetState().Fluid
                break
        if Fluid is None:
            raise ValueError('StatePanel not found in Inputs Toolbook')
        
        #You can only inject the same refrigerant as at the suction so fix the fluid
        self.state = pdsim_panels.StatePanel(self, Fluid=Fluid, Fluid_fixed = True)
        
        self.Llabel,self.Lval = LabeledItem(self, label='Length of injection line',value='1.0')
        self.IDlabel,self.IDval = LabeledItem(self, label='Inner diameter of injection line',value='0.01')
        line_sizer = wx.FlexGridSizer(cols = 2)
        line_sizer.AddMany([self.Llabel,self.Lval])
        line_sizer.AddMany([self.IDlabel,self.IDval])
        
        self.RemoveButton = wx.Button(self,label='Remove Line')
        self.RemoveButton.Bind(wx.EVT_BUTTON, lambda event: self.Parent.RemoveInjection(self))
        
        self.SizerBox = wx.StaticBox(self, label = "Injection line #"+str(index))
        self.SBSSizer = wx.StaticBoxSizer(self.SizerBox, wx.VERTICAL)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.RemoveButton)
        
        text = wx.StaticText(self, label='Parameters:')
        font = text.GetFont()
        font.SetUnderlined(True)
        text.SetFont(font)
        sizer.Add(text)
        sizer.AddSpacer(10)
        sizer.Add(line_sizer)
        sizer.AddSpacer(10)
        text = wx.StaticText(self, label='State:')
        font = text.GetFont()
        font.SetUnderlined(True)
        text.SetFont(font)
        sizer.Add(text)
        sizer.Add(self.state)
        text = wx.StaticText(self, label='Injection Ports:')
        font = text.GetFont()
        font.SetUnderlined(True)
        text.SetFont(font)
        sizer.Add(text)
        IPP = InjectionPortPanel(self, index = 1)
        self.ports_list = [IPP]
        sizer.Add(IPP)
        self.InnerSizer = sizer
        self.SBSSizer.Add(sizer)
        self.SBSSizer.Layout()
        self.SetSizer(self.SBSSizer)
        self.Nports = 1
        
    def OnRemovePort(self, removed_port = None):
        #Store a dictionary of partners for each port
        partner_dict = {}
        for port in self.ports_list:
            #Get the index
            index_partner = port.SymmTarget.GetStringSelection()
            try:
                #Get the partner panel
                partner = self.ports_list[int(index_partner)-1]
            except ValueError:
                partner = None
                
            #If partner still exists after removing the port, keep a reference
            #to the port
            if partner == removed_port:
                #Entry points to nothing
                partner_dict[port.index] = None
            else:
                #Entry points to partner instance
                partner_dict[port.index] = partner
        
        #Can't remove the first element
        if self.Nports > 1:
            I_removed = self.ports_list.index(removed_port)
            self.ports_list.remove(removed_port)
            removed_port.Destroy()
            self.SBSSizer.Layout()
            self.Refresh()
            self.Nports -= 1
            self.Fit()
            
            #renumber the ports starting at 1
            for i,port in enumerate(self.ports_list):
                port.set_index(i+1)
            
            # Shift the indices down for all the elements above the removed port
            # in the partner_dictionary
            partner_dict.pop(I_removed+1) #partner_dict uses 1-based indexing
            for i in range(I_removed+1,len(self.ports_list)+1):
                partner_dict[i] = partner_dict[i+1]
            partner_dict.pop(len(self.ports_list)+1)
                
            Nports = len(self.ports_list)
            for port in self.ports_list:
                    
                port.SymmTarget.Clear()
                port.SymmTarget.Append('None')
                for i in range(1, Nports+1):
                    if not port.index == i:
                        #Add this new port to the list of possible partners
                        port.SymmTarget.Append(str(i))
                
                partner = partner_dict[port.index]
                #Reset the partner if it had a partner
                if partner is not None:
                    port.SymmTarget.SetStringSelection(str(partner.index))
                else:
                    port.SymmTarget.SetStringSelection('None')
        
        #Update the elements in the parametric table
        Main = self.GetTopLevelParent()
        items = Main.collect_parametric_terms()
        Main.MTB.SolverTB.update_parametric_terms(items)
        
    def OnAddPort(self, event = None):
        IPP = InjectionPortPanel(self, index = len(self.ports_list)+1)
        self.SBSSizer.Add(IPP)
        self.ports_list.append(IPP)
        self.SBSSizer.Layout()
        self.Nports += 1
        self.GetSizer().Layout()
        self.Refresh()
        self.Fit()
        # When you add a port, it cannot be a partner of any other chamber at
        # instantiation
        Nports = len(self.ports_list)
        for port in self.ports_list:
            
            index_partner = None
            if not port.SymmTarget.GetStringSelection() == 'None':
                #Get the index
                index_partner = port.SymmTarget.GetStringSelection()
                
            port.SymmTarget.Clear()
            port.SymmTarget.Append('None')
            for i in range(1, Nports+1):
                if not port.index == i:
                    #Add this new port to the list of possible partners
                    port.SymmTarget.Append(str(i))
            
            #Reset the value if it had a partner
            if index_partner is not None:
                port.SymmTarget.SetStringSelection(index_partner)
            else:
                port.SymmTarget.SetStringSelection('None')
        
        #Update the elements in the parametric table
        Main = self.GetTopLevelParent()
        items = Main.collect_parametric_terms()
        Main.MTB.SolverTB.update_parametric_terms(items)
        
class InjectionInputsPanel(pdsim_panels.PDPanel):
    """
    The container panel for all the injection ports and injection data 
    """ 
    def __init__(self, parent, **kwargs):
        pdsim_panels.PDPanel.__init__(self,parent,**kwargs)
        
        #Add the header row of buttons
        self.View = wx.Button(self, label='View')
        self.View.Bind(wx.EVT_BUTTON, self.OnView)
        self.AddInjection = wx.Button(self, label='Add Injection Line')
        self.AddInjection.Bind(wx.EVT_BUTTON, self.OnAddInjection)
        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        buttons_sizer.Add(self.AddInjection)
        buttons_sizer.Add(self.View)
        
        sizer = wx.FlexGridSizer(cols = 1)
        sizer.Add(buttons_sizer)
        sizer.AddSpacer(10)
        sizer.Layout()
        self.SetSizer(sizer)
        self.Nterms = 0
        self.Lines = []
        
    def OnAddInjection(self, event = None):
        """
        Add an injection line to the injection panel
        """
        IE = InjectionElementPanel(self,self.Nterms+1)
        self.GetSizer().Add(IE)
        self.Lines.append(IE)
        self.Nterms += 1
        self.GetSizer().Layout()
        self.Refresh()
        
        #Update the elements in the parametric table
        Main = self.GetTopLevelParent()
        items = Main.collect_parametric_terms()
        Main.MTB.SolverTB.update_parametric_terms(items)
        
        
    def RemoveInjection(self, injection):
        """
        Remove the given injection term
        """
        self.Lines.remove(injection)
        injection.Destroy()
        self.Nterms -= 1
        #Renumber the injection panels
        I=1
        for child in self.Children:
            if isinstance(child,InjectionElementPanel):
                child.SizerBox.SetLabel("Injection line #"+str(I))
                I+=1
        self.GetSizer().Layout()
        self.Refresh()
        
        #Update the elements in the parametric table
        Main = self.GetTopLevelParent()
        items = Main.collect_parametric_terms()
        Main.MTB.SolverTB.update_parametric_terms(items)
        
    def OnView(self, event):
        geo = self.GetTopLevelParent().MTB.InputsTB.panels[0].Scroll.geo
        dlg = InjectionViewerDialog(pi/2,geo)
        
        #IEPs are children that are instances of InjectionElementPanel class
        IEPs = [child for child in self.Children if isinstance(child,InjectionElementPanel)]
        for IEP in IEPs:
            for child in IEP.Children:
                if isinstance(child,InjectionPortPanel):
                    phi,inner_outer,check_valve = child.get_values()
                    dlg.add_port(phi, inner_outer)
                    
        dlg.ShowModal()
        dlg.Destroy()
        
    def post_prep_for_configfile(self):
        """
        
        Returns
        -------
        a \n delimited string to be written to file
        """
        
        s = []
        s += ['Nlines = '+str(self.Nterms)]
        for i in range(self.Nterms):
            #: a string representation of the index
            I = str(i+1)
            
            #These things are for the line
            s += ['Lline_'+I+' = '+str(self.Lines[i].Lval.GetValue())]
            s += ['IDline_'+I+' = '+str(self.Lines[i].IDval.GetValue())]
            State = self.Lines[i].state.GetState()
            s += ['State_'+I+' = '+State.Fluid+','+str(State.T)+','+str(State.rho)]
            
            #Then the things related to the ports for this line
            s += ['Nports_'+I+' = '+str(len(self.Lines[i].ports_list))]
            for j in range(self.Lines[i].Nports):
                J = str(j+1)
                #Get the port itself for code compactness
                port = self.Lines[i].ports_list[j]
                
                #The things that are for the port
                s += ['phi_'+I+'_'+J+' = '+str(port.phi_inj_port.GetValue())]
                inv = port.involute.GetValue()
                if inv == 'Inner involute':
                    s += ['involute_'+I+'_'+J+' = i']
                elif inv == 'Outer involute':
                    s += ['involute_'+I+'_'+J+' = o']
                else:
                    raise ValueError
                
                s += ['check_'+I+'_'+J+' = '+str(port.check_valve.IsChecked())]
                s += ['symmetric_'+I+'_'+J+' = '+str(port.SymmTarget.GetStringSelection())]
            
        return '\n'.join(s)+'\n'
        
    def build_from_configfile_items(self, configfile_items):
        """
        Get parameters from the configfile section for this plugin
        
        Parameters
        ----------
        configfile_section : list of 2-element tuples, first element is key, second is value as a string
        
        """
        #Convert List of tuples to dict
        configfile_dict = {param:val for param,val in configfile_items}
        
        if u'Nlines' in configfile_dict:
            N = int(configfile_dict.pop(u'Nlines'))
            for i in range(N):
                I = str(i+1)
                self.OnAddInjection()
                #Get a pointer to the last IEP (the one just added)
                IEP = self.Lines[-1]
                #Set the line length in the GUI
                Lline = float(configfile_dict.pop(u'Lline_'+I))
                IEP.Lval.SetValue(str(Lline))
                #Set the line ID in the GUI
                IDline = float(configfile_dict.pop(u'IDline_'+I))
                IEP.IDval.SetValue(str(IDline))
                #Set the State in the GUI
                State_string = configfile_dict.pop(u'State_'+I)
                Fluid,T,rho = State_string.split(',')
                IEP.state.set_state(str(Fluid), T = float(T), D = float(rho))
                #Get the number of ports for this line
                Nports = int(configfile_dict.pop(u'Nports_'+I))
                for j in range(Nports):
                    J = str(j+1)
                    if j>0:
                        IEP.OnAddPort()
                    #Get a pointer to the port panel
                    port = IEP.ports_list[-1]
                    
                    #Get the angle
                    phi = configfile_dict.pop(u'phi_'+I+'_'+J)
                    
                    #Get the neighboring involute
                    inner_outer = configfile_dict.pop(u'involute_'+I+'_'+J)
                    
                    #Get the checkvalve flag
                    check_valve = configfile_dict.pop(u'check_'+I+'_'+J)
                    
                    #Get the checkvalve flag
                    symmetric = configfile_dict.pop(u'symmetric_'+I+'_'+J)
                    
                    #Set the values in the panel
                    port.set_values(phi, inner_outer, check_valve, symmetric)
                
            #Check if any terms are left, if so raise ValueError
            if configfile_dict:
                raise ValueError('Unmatched term in configfile_items remaining:'+str(configfile_dict))
    
    def get_additional_parametric_terms(self):
        
        #: the list of terms
        _T = []
        
        #IEPs are children of injection_panel that are instances of InjectionElementPanel class
        IEPs = [child for child in self.Children if isinstance(child,InjectionElementPanel)]
        for i,IEP in enumerate(IEPs):
            I = str(i+1)
            
            _T += [dict(attr = 'injection_state_pressure_' + I,
                        text = 'Injection pressure #' + I + ' [kPa]',
                        parent = self),
                   dict(attr = 'injection_state_sat_temp_' + I,
                        text = 'Injection saturated temperature (dew) #' + I + ' [K]',
                        parent = self),
                   dict(attr = 'injection_state_temp_' + I,
                        text = 'Injection temperature #' + I + ' [K]',
                        parent = self),
                   dict(attr = 'injection_state_superheat_' + I,
                        text = 'Injection superheat #' + I + ' [K]',
                        parent = self),
                ]
                
            Ports = [c for c in IEP.Children if isinstance(c,InjectionPortPanel)]
            for j,child in enumerate(Ports):
                J = str(j+1)
                _T += [dict(attr = 'injection_phi_'+I+'_'+J,
                            text = 'Injection port angle #'+I+':'+J+' [rad]',
                            parent = self)]
                
        return _T
                
        
    def apply_additional_parametric_terms(self, attrs, vals, panel_items):
        """
        Set the terms in the panel based on the additional parametric terms
        """
        
        panel_attrs = [panel_item['attr'] for panel_item in panel_items]
        
        phi_params = [(par,val) for par, val in zip(attrs,vals) if par.startswith('injection_phi')]
        num_phi_params = len(phi_params)        
        if num_phi_params > 0:
            #Unzip the parameters (List of tuples -> tuple of lists)
            phi_attrs, phi_vals = zip(*phi_params)
            
            # Remove all the entries that correspond to the angles 
            # we need them and don't want to set them in the conventional way
            for a in phi_attrs:
                i = attrs.index(a)
                vals.pop(i)
                attrs.pop(i)
                
            for attr,val in zip(phi_attrs, phi_vals):

                # Term might look like something like 'injection_phi_1_2'
                # i would be 0, j would be 1
                #indices are zero-based
                j = int(attr.rsplit('_',1)[1])-1
                i = int(attr.rsplit('_',2)[1])-1
                
                self.Lines[i].ports_list[j].phi_inj_port.SetValue(str(val))
    
        # First check about the injection state; if two state related terms are 
        # provided, use them to fix the injection state
        inj_state_params = [(par,val) for par,val in zip(attrs,vals) if par.startswith('injection_state')]
        num_inj_state_params = len(inj_state_params)
        
        i = 0
        I = '1'
        #Get a copy of the state from the StatePanel
        inletState = self.Lines[i].state.GetState()
        
        if num_inj_state_params > 0:
            #Unzip the parameters (List of tuples -> tuple of lists)
            state_attrs, state_vals = zip(*inj_state_params)
            
        if num_inj_state_params == 2:
            # Remove all the entries that correspond to the injection state - 
            # we need them and don't want to set them in the conventional way
            for a in state_attrs:
                vals.pop(attrs.index(a))
                attrs.pop(attrs.index(a))
            
            #Temperature and pressure provided
            if 'injection_state_temp_'+I in state_attrs and 'injection_state_pressure_'+I in state_attrs:
                injection_temp = state_vals[state_attrs.index('injection_state_temp_'+I)]
                injection_pressure = state_vals[state_attrs.index('injection_state_pressure_'+I)]
                self.Lines[i].state.set_state(inletState.Fluid,
                                              T=injection_temp, 
                                              P=injection_pressure)
                
            #Dew temperature and superheat provided
            elif 'injection_state_sat_temp_'+I in state_attrs and 'injection_state_superheat_'+I in state_attrs:
                injection_sat_temp = state_vals[state_attrs.index('injection_state_sat_temp_'+I)]
                injection_superheat = state_vals[state_attrs.index('injection_state_superheat_'+I)]
                injection_temp = injection_sat_temp + injection_superheat
                import CoolProp.CoolProp as CP
                injection_pressure = CP.Props('P','T',injection_sat_temp,'Q',1.0,inletState.Fluid)
                self.Lines[i].state.set_state(inletState.Fluid,
                                              T=injection_temp, 
                                              P=injection_pressure)
                
            else:
                raise ValueError('Invalid combination of injection states: '+str(state_attrs))
            
        elif num_inj_state_params == 1:
            import textwrap
            string = textwrap.dedent(
                     """
                     Sorry but you need to provide two variables for the injection
                     state in parametric table to fix the state.  
                     
                     If you want to just modify the saturated temperature, add the superheat as a
                     variable and give it one element in the parametric table
                     """
                     )
            dlg = wx.MessageDialog(None,string)
            dlg.ShowModal()
            dlg.Destroy()
            raise ValueError('Must provide two state variables in the parametric table for injection line')
            
        elif num_inj_state_params >2:
            raise ValueError ('Only two inlet state parameters can be provided in parametric table')
    
        return attrs,vals
        
class ScrollInjectionPlugin(pdsim_plugins.PDSimPlugin):
    """
    A plugin that adds the injection ports for the scroll compressor
    """
    
    #: A short description of the plugin 
    short_description = 'Refrigerant injection for scroll'
        
    def should_enable(self):
        """
        Only enable if it is a scroll type compressor
        """
        if not self.GUI.SimType.lower() == 'scroll':
            return False
        else:
            return True
        
    def build_from_configfile_items(self, configfile_items):
        """
        Take in the dictionary of items from the configfile and pass
        them along to the injection_panel
         
        Parameters
        ----------
        configfile_items : dict
        
        """
        self.injection_panel.build_from_configfile_items(configfile_items)
        
    def activate(self, event = None):
        #: The inputs toolbook that contains all the input panels
        ITB = self.GUI.MTB.InputsTB
        
        if not self._activated:
            #Add the panel to the inputs panel
            #name is the internal name, also used in saving and loading 
            # config files
            self.injection_panel = InjectionInputsPanel(ITB, name = 'Plugin:ScrollInjectionPlugin')
            ITB.AddPage(self.injection_panel,"Injection")
            self._activated = True
        else:
            page_names = [ITB.GetPageText(I) for I in range(ITB.GetPageCount())]
            I = page_names.index("Injection")
            ITB.RemovePage(I)
            self.injection_panel.Destroy()
            self._activated = False
            
    def apply(self, ScrollComp, **kwargs):
        """
        Add the necessary things for the scroll compressor injection
        
        Parameters
        ----------
        ScrollComp : Scroll instance
        """
        
        #Add a struct (empty class with no methods)
        ScrollComp.injection = struct()
        #Empty dictionaries for the port terms
        ScrollComp.injection.phi = {}
        ScrollComp.injection.inner_outer = {}
        ScrollComp.injection.check_valve = {}
            
        #IEPs are children of injection_panel that are instances of InjectionElementPanel class
        IEPs = [child for child in self.injection_panel.Children if isinstance(child,InjectionElementPanel)]
        for i,IEP in enumerate(IEPs):
            L = float(IEP.Lval.GetValue())
            ID = float(IEP.IDval.GetValue())
            injState = IEP.state.GetState().copy()
            V_tube = L*pi*ID**2/4.0
            
            CVkey = 'injCV.'+str(i+1)
            #Add the control volume for the injection line
            ScrollComp.add_CV(ControlVolume(key = CVkey,
                                            VdVFcn = ScrollComp.V_injection,
                                            VdVFcn_kwargs = dict(V_tube = V_tube),
                                            initialState = injState,
                                            )
                              )
            
            #Add the tube for the injection line
            ScrollComp.add_tube(Tube(key1='injection_line.'+str(i+1)+'.1',
                                     key2='injection_line.'+str(i+1)+'.2',
                                     L=L,
                                     ID=ID,
                                     mdot=0.001, 
                                     State1=ScrollComp.CVs[CVkey].State.copy(),
                                     fixed=1,
                                     TubeFcn=ScrollComp.TubeCode
                                     )
                                )
            
            #Add the flow model between the injection line tube and the injection CV 
            ScrollComp.add_flow(FlowPath(key1='injection_line.'+str(i+1)+'.2',
                                         key2=CVkey,
                                         MdotFcn=ScrollComp.IsentropicNozzleFM,
                                         MdotFcn_kwargs = dict(A = pi*ID**2/4)
                                         )
                                )
            
            
            
            Ports = [c for c in IEP.Children if isinstance(c,InjectionPortPanel)]
            for j,child in enumerate(Ports):
                phi,inner_outer,check_valve = child.get_values()
                
                #Figure out which CV are in contact with this location for the injection port
                partner_key_start = ScrollComp._get_injection_CVkey(phi, 0*pi, inner_outer)
                partner_key_end = ScrollComp._get_injection_CVkey(phi, 2*pi, inner_outer)
                
                #Store the port parameters for writing in the collect_output_terms function
                k = str(i+1)+','+str(j+1)
                ScrollComp.injection.phi[k]=phi
                ScrollComp.injection.inner_outer[k]=inner_outer
                ScrollComp.injection.check_valve[k]=check_valve
                
                #Add the CV that start and end the rotation connected to the port
                for partner_key in [partner_key_start, partner_key_end]:
                    #Injection flow paths
                    ScrollComp.add_flow(FlowPath(key1= partner_key, 
                                                 key2 = CVkey, 
                                                 MdotFcn=ScrollComp.Injection_to_Comp,
                                                 MdotFcn_kwargs = dict(phi = phi,
                                                                       inner_outer = inner_outer,
                                                                       check_valve = check_valve)
                                                )
                                        )
                        
    def post_process(self, sim):
        """
        Post-process the results from the simulation in order to calculate any parameters that
        are required
        
        This function will be called by OnIdle in GUI Main frame when run finishes
        """

        sim.injection.massflow={}
        #:the ratio of the injection flow rate to the suction flow rate
        sim.injection.flow_ratio={}
        #injection pressure
        sim.injection.pressure={}
        #injection temperature
        sim.injection.temperature={}
        
        #The tubes that are injection tubes have a key1 that starts with 'injection_line'
        ITubes = [T for T in sim.Tubes if T.key1.startswith('injection_line')]
        
        for i,Tube in enumerate(ITubes):
            key = Tube.key1
            sim.injection.massflow[i+1]=sim.FlowsProcessed.mean_mdot[key]
            sim.injection.flow_ratio[i+1]=(sim.injection.massflow[i+1]/
                                           sim.mdot)
            sim.injection.pressure[i+1] = Tube.State1.p
            sim.injection.temperature[i+1] = Tube.State1.T
                
        #Save a local copy of a pointer to the simulation
        self.simulation = sim
    
    def collect_output_terms(self):
        """
        Return terms for the output panel in the GUI
        
        Happens after even the post-processing
        """
        _T = []
        
        #These parameters pertain to each of the injection lines
        for i in self.simulation.injection.massflow:
            _T.append(dict(attr = "injection.massflow["+str(i)+"]",
                           text = "Injection line #"+str(i)+" mass flow [kg/s]",
                           parent = self
                           )
                      )
            _T.append(dict(attr = "injection.flow_ratio["+str(i)+"]",
                           text = "Injection line #"+str(i)+" flow ratio to suction flow [-]",
                           parent = self
                           )
                      )
            _T.append(dict(attr = "injection.pressure["+str(i)+"]",
                           text = "Injection line #"+str(i)+" pressure [kPa]",
                           parent = self
                           )
                      )
            _T.append(dict(attr = "injection.temperature["+str(i)+"]",
                           text = "Injection line #"+str(i)+" temperature [K]",
                           parent = self
                           )
                      )
        
        #These are defined for each port
        for _i_j in self.simulation.injection.phi:
            
            #Split the key back into its integer components (still as strings)
            _i,_j = _i_j.split(',')
            
            #Add the output things for the ports
            _T.append(dict(attr = "injection.phi['"+_i+","+_j+"']",
                           text = "Injection inv. angle #" + _i + "," + _j + " [rad]",
                           parent = self
                           )
                      )
            _T.append(dict(attr = "injection.inner_outer['"+_i+","+_j+"']",
                           text = "Injection involute #" + _i + "," + _j + " [-]",
                           parent = self
                           )
                      )
        
        return _T
        
        
        