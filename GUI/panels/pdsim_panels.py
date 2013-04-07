# -*- coding: latin-1 -*-

# Python imports
import warnings, codecs, textwrap,os, itertools, difflib, zipfile
from multiprocessing import Process

# wxPython imports
import wx
from wx.lib.mixins.listctrl import CheckListCtrlMixin,TextEditMixin,ListCtrlAutoWidthMixin

import CoolProp
from CoolProp.State import State
from CoolProp import CoolProp as CP

import numpy as np

import matplotlib as mpl
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as WXCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2Wx as WXToolbar

from PDSim.scroll import scroll_geo
from PDSim.scroll.plots import plotScrollSet, ScrollAnimForm
from PDSim.misc.datatypes import AnnotatedValue
from datatypes import AnnotatedGUIObject, HeaderStaticText

import PDSimGUI

import h5py
import quantities as pq

length_units = {
                'Meter': pq.length.m,
                'Millimeter': pq.length.mm,
                'Micrometer' : pq.length.um,
                'Centimeter' : pq.length.cm,
                'Inch' : pq.length.inch,
                }

area_units = {
                'Square Meter': pq.length.m**2,
                'Square Micrometer' : pq.length.um**2,
                'Square Centimeter' : pq.length.cm**2,
                'Square Inch' : pq.length.inch**2,
                }

volume_units = {
                'Cubic Meter': pq.length.m**3,
                'Cubic Micrometer' : pq.length.um**3,
                'Cubic Centimeter' : pq.length.cm**3,
                'Cubic Inch' : pq.length.inch**3,
                }

pressure_units = {
                  'kPa' : pq.kPa,
                  'psia' : pq.psi
                  }
rev = pq.UnitQuantity('revolution', 2*np.pi*pq.radians, symbol='rev')

rotational_speed_units ={
                         'Radians per second': pq.radians/pq.sec,
                         'Radians per minute': pq.radians/pq.min,
                         'Revolutions per second': rev/pq.sec,
                         'Revolutions per minute': rev/pq.min,
                         }

temperature_units = {
                     'Kelvin' : np.nan,
                     'Celsius' : np.nan,
                     'Fahrenheit' : np.nan,
                     'Rankine': np.nan
                     }


class InputsToolBook(wx.Toolbook):
    
    def get_script_chunks(self):
        """
        Pull all the values out of the child panels, using the values in 
        self.items and the function get_script_chunks if the panel implements
        it
        
        The values are written into the script file that will be execfile-d
        """
        chunks = []
        for panel in self.panels:
            chunks.append('#############\n# From '+panel.Name+'\n############\n')
            if hasattr(panel,'get_script_params'):
                chunks.append(panel.get_script_params())
            if hasattr(panel,'get_script_chunks'):
                chunks.append(panel.get_script_chunks())
        return chunks

class UnitConvertor(wx.Dialog):
    def __init__(self, value, default_units, type = None, TextCtrl = None):
        wx.Dialog.__init__(self, None, title='Convert units')
        
        self.default_units = default_units
        self.__is_temperature__ = False
        if default_units in length_units or type == 'length':
            self.unit_dict = length_units
        elif default_units in area_units or type == 'area':
            self.unit_dict = area_units
        elif default_units in volume_units or type == 'volume':
            self.unit_dict = volume_units
        elif default_units in rotational_speed_units or type == 'rotational_speed':
            self.unit_dict = rotational_speed_units
        elif default_units in pressure_units or type == 'pressure':
            self.unit_dict = pressure_units
        elif default_units in temperature_units or type == 'temperature':
            self.unit_dict = temperature_units
            self.__is_temperature__ = True
        else:
            raise KeyError('Sorry your units '+default_units+' did not match any of the unit terms')
            
        self.txt = wx.TextCtrl(self, value=str(value))
        self.units = wx.Choice(self)
        self.units.AppendItems(sorted(self.unit_dict.keys()))
        if default_units in self.units.GetStrings():
            self.units.SetStringSelection(default_units)
        else:
            raise KeyError
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.txt)
        sizer.Add(self.units)
        self.SetSizer(sizer)
        self.Fit()
        self._old_units = default_units
        
        self.Bind(wx.EVT_CHOICE, self.OnSwitchUnits, self.units)

    #Bind a key-press event to all objects to get Esc 
        children = self.GetChildren()
        for child in children:
            child.Bind(wx.EVT_KEY_UP,  self.OnKeyPress)
        
    def OnKeyPress(self,event=None):
        """ cancel if Escape key is pressed """
        event.Skip()
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        elif event.GetKeyCode() == wx.WXK_RETURN:
            self.EndModal(wx.ID_OK)
                    
    def OnSwitchUnits(self, event):
        if not self.__is_temperature__:
            old = float(self.txt.GetValue()) * self.unit_dict[self._old_units]
            new_units_str = self.units.GetStringSelection()
            new_units = self.unit_dict[new_units_str]
            old.units = new_units
            self._old_units = new_units_str
            self.txt.SetValue(str(old.magnitude))
        else:
            old_val = float(self.txt.GetValue())
            new_units_str = self.units.GetStringSelection()
            new_val = self._temperature_convert(self._old_units, old_val, new_units_str)
            self._old_units = new_units_str
            self.txt.SetValue(str(new_val))
            
    def get_value(self):
        """
        Return a string with value in the original units for use in calling function to dialog
        """
        if not self.__is_temperature__:
            old = float(self.txt.GetValue()) * self.unit_dict[self._old_units]
            old.units = self.unit_dict[self.default_units]
            return str(old.magnitude)
        else:
            old_val = float(self.txt.GetValue())
            return str(self._temperature_convert(self._old_units, old_val, self.default_units))
    
    def _temperature_convert(self, old, old_val, new):
        """
        Internal method to convert temperature
        
        Parameters
        ----------
        old : string
        old_val : float
        new : string
        """
        #convert old value to Celsius
        # also see: http://en.wikipedia.org/wiki/Temperature
        if old == 'Fahrenheit':
            celsius_val = (old_val-32)*5.0/9.0
        elif old == 'Kelvin':
            celsius_val = old_val-273.15
        elif old == 'Rankine':
            celsius_val = (old_val-491.67)*5.0/9.0
        elif old == 'Celsius':
            celsius_val = old_val
            
        #convert celsius to new value
        if new == 'Celsius':
            return celsius_val
        elif new == 'Fahrenheit':
            return celsius_val*9.0/5.0+32.0
        elif new == 'Kelvin':
            return celsius_val+273.15
        elif new == 'Rankine':
            return (celsius_val+273.15)*9.0/5.0
        
def mathtext_to_wxbitmap(s):
    #The magic from http://matplotlib.org/examples/user_interfaces/mathtext_wx.html?highlight=button
    from matplotlib.mathtext import MathTextParser
    
    mathtext_parser = MathTextParser("Bitmap")
    ftimage, depth = mathtext_parser.parse(s, 100)
    return wx.BitmapFromBufferRGBA(ftimage.get_width(), 
                                   ftimage.get_height(),
                                   ftimage.as_rgba_str()
                                   )
        
def EquationButtonMaker(LaTeX, parent, **kwargs):
    """
    A Convenience function to generate a button with LaTeX as its image
    
    LaTeX : string
    parent : wx.Window
    
    kwargs passed to BitmapButton constructor 
    """
    return wx.BitmapButton(parent, bitmap = mathtext_to_wxbitmap(LaTeX), **kwargs)
    
def LaTeXImageMaker(LaTeX,parent,**kwargs):
    return wx.StaticBitmap(parent, bitmap = mathtext_to_wxbitmap(LaTeX), **kwargs)        
        
class PlotPanel(wx.Panel):
    def __init__(self, parent, toolbar = False, **kwargs):
        wx.Panel.__init__(self, parent, **kwargs)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.figure = mpl.figure.Figure(dpi=100, figsize=(2, 2))
        self.canvas = WXCanvas(self, -1, self.figure)
        
        sizer.Add(self.canvas)
        
        if toolbar:
            self.toolbar = WXToolbar(self.canvas)
            self.toolbar.Realize()
            sizer.Add(self.toolbar)
            
        self.SetSizer(sizer)
        sizer.Layout()

class PDPanel(wx.Panel):
    """
    A base class for panel with some goodies thrown in 
    
    Not intended for direct instantiation, rather it should be 
    subclassed, like in :class:`recip_panels.GeometryPanel`
    
    Loading from configuration file
    -------------------------------
    Method (A)
    
    Any subclassed PDPanel must either store a list of items as 
    ``self.items`` where the entries are dictionaries with at least the entries:
    
    - ``text``: The text description of the term 
    - ``attr``: The attribute in the simulation class that is linked with this term
    
    Other terms that can be included in the item are:
    - ``tooltip``: The tooltip to be attached to the textbox
    
    Method (B)
    
    The subclassed panel can provide the functions post_prep_for_configfile
    and post_get_from_configfile, each of which take no inputs.
    
    In post_prep_for_configfile, the subclassed panel can package up its elements
    into a form that can then be re-created when post_get_from_configfile is
    called
    
    
    Saving to configuration file
    ----------------------------
    
    Adding terms to parametric table
    --------------------------------
    
    """
    def __init__(self,*args,**kwargs):
        wx.Panel.__init__(self,*args,**kwargs)
        self.name=kwargs.get('name','')
        
        # Get the main frame
        self.main = self.GetTopLevelParent()
        
    def _get_item_by_attr(self, attr):
        if hasattr(self,'items'):
            for item in self.items:
                if item['attr'] == attr:
                    return item
        raise ValueError('_get_item_by_attr failed')
        
    def _get_value(self,thing):
        #This first should work for wx.TextCtrl
        if hasattr(thing,'GetValue'):
            value=str(thing.GetValue()).strip()
            try:
                return float(value)
            except ValueError:
                return value
        elif hasattr(thing,'GetSelectionString'):
            value=thing.GetSelection()
            try:
                return float(value)
            except ValueError:
                return value
             
    def get_script_params(self):
        if not hasattr(self,'items'):
            return ''
        else:
            items = self.items
        
        if hasattr(self,'skip_list'):
            # Don't actually set these attributes (they might over-write 
            # methods or attributes in the simulation)
            items = [item for item in items if item['attr'] not in self.skip_list()]
        
        values = ''
        for item in items:
            values += 'sim.{attr:s} = {val:s}\n'.format(attr = item['attr'],
                                                        val = str(self._get_value(item['textbox'])))
        
        return values
    
    def ConstructItems(self, items, sizer, configdict = None, descdict=None, parent = None):
        
        """
        Parameters
        ----------
        items : a list of dictionaries
            Each item is a dictionary of values with the keys:
                attr : PDSim attribute
        sizer : wx.Sizer
            The sizer to add the items to
        configdict : dictionary
            The configuration value dictionary that was pulled from the file
        descdict : dictionary
            The configuration description dictionary that was pulled from the file
        parent : wx.Window
            The parent of the items, default is this panel
        """
        for item in items:
            
            if parent is None:
                parent = self
            
            if 'val' not in item and configdict is not None:
                k = item['attr']
                if k not in configdict:
                    #Returns a dictionary of values and a dictionary of descriptions
                    d,desc = self.get_from_configfile(self.name, k, default = True)
                    #Get the entries for the given key
                    val,item['text'] = d[k],desc[k]
                else:
                    val = configdict[k]
                    item['text'] = descdict[k]
            else:
                d,desc = self.get_from_configfile(self.name, item['attr'])
                #Get the entries for the given key
                val,item['text'] = d[k],desc[k]
                
            label=wx.StaticText(parent, -1, item['text'])
            sizer.Add(label, 1, wx.EXPAND)
            textbox=wx.TextCtrl(parent, -1, str(val))
            sizer.Add(textbox, 1, wx.EXPAND)
            item.update(dict(textbox=textbox, label=label))
            
            caption = item['text']
            if caption.find(']')>=0 and caption.find(']')>=0: 
                units = caption.split('[',1)[1].split(']',1)[0]
                unicode_units = unicode(units)
                if unicode_units == u'm':
                    textbox.default_units = 'Meter'
                elif unicode_units == u'm\xb2':
                    textbox.default_units = 'Square Meter'
                elif unicode_units == u'm\xb3':
                    textbox.default_units = 'Cubic Meter'
                elif units == 'rad/s':
                    textbox.default_units = 'Radians per second'
                self.Bind(wx.EVT_CONTEXT_MENU,self.OnChangeUnits,textbox)     
                
    def construct_items(self, annotated_objects, sizer = None, parent = None):
        
        """
        Parameters
        ----------
        annotated_objects : a list of `AnnotatedValue <PDSim.misc.datatypes.AnnotatedValue>`
        sizer : wx.Sizer
            The sizer to add the wx elements to
        parent : wx.Window
            The parent of the items, default is this panel
            
        Returns
        -------
        annotated_GUI_objects : a list of `GUIAnnotatedObject` derived from the input ``annotated_objects`` 
        """
        
        # Default to parent it to this panel
        if parent is None:
            parent = self
            
        # Output list of annotated GUI objects
        annotated_GUI_objects = []
        
        # Loop over the objects
        for o in annotated_objects:
            
            # Type-check
            if not isinstance(o, AnnotatedValue):
                raise TypeError('object of type [{t:s}] is not an AnnotatedValue'.format(t = type(o)))
                
            # Build the GUI objects
            label=wx.StaticText(parent, -1, o.annotation)
            
            if sizer is not None:
                # Add the label to the sizer
                sizer.Add(label, 1, wx.EXPAND)

            # If the input is a boolean value, make a check box
            if isinstance(o.value,bool):
                # Build the checkbox
                checkbox = wx.CheckBox(parent)
                # Set its value
                checkbox.SetValue(o.value)
                
                if sizer is not None:
                    # Add to the sizer
                    sizer.Add(checkbox, 1, wx.EXPAND)
                
                # Add to the annotated objects
                annotated_GUI_objects.append(AnnotatedGUIObject(o,checkbox))
            
            # Otherwise make a TextCtrl 
            else:
                # Create the textbox
                textbox=wx.TextCtrl(parent, value = str(o.value))
                
                if sizer is not None:
                    # Add it to the sizer
                    sizer.Add(textbox, 1, wx.EXPAND)
                
                # Units are defined for the item
                if o.units:
                    unicode_units = unicode(o.units)
                    textbox.default_units = ''
                    if unicode_units == u'm':
                        textbox.default_units = 'Meter'
                    elif unicode_units == u'm^2':
                        textbox.default_units = 'Square Meter'
                    elif unicode_units == u'm^3':
                        textbox.default_units = 'Cubic Meter'
                    elif unicode_units == u'rad/s':
                        textbox.default_units = 'Radians per second'
                    
                    #If it has units bind the unit changing callback on right-click
                    if textbox.default_units:
                        self.Bind(wx.EVT_CONTEXT_MENU,self.OnChangeUnits,textbox)  
                
                annotated_GUI_objects.append(AnnotatedGUIObject(o,textbox))
            
        if len(annotated_GUI_objects) == 1:
            return annotated_GUI_objects[0]
        else:
            return annotated_GUI_objects
              
        
    def prep_for_configfile(self):
        """
        Writes the panel to a format ready for writing to config file
        using the entries in ``self.items``.  
        
        If there are other fields that need to get saved to file, the panel 
        can provide the ``post_prep_for_configfile`` function and add the additional fields 
        
        This function will call the ``post_prep_for_configfile`` if the subclass has it
        and add to the returned string
        """
        if self.name=='':
            return ''
            
        if not hasattr(self,'items'):
            self.items=[]
        
        s='['+self.name+']\n'
        
        for item in self.items:
            val = item['textbox'].GetValue()
            # Description goes into the StaticText control
            try:
                int(val)
                type_='int'
            except ValueError:
                try: 
                    float(val)
                    type_='float'
                except ValueError:
                    type_='string'
            s+=item['attr']+' = '+type_+','+item['textbox'].GetValue().encode('latin-1')+','+item['text']+'\n'
            
        if hasattr(self,'post_prep_for_configfile'):
            s+=self.post_prep_for_configfile()
        
        s=s.replace('%','%%')
        return s
           
    def _get_from_configfile(self, name, value):
        """
        Takes in a string from the config file and figures out how to parse it
        
        Returns
        -------
        d : value
            Variable type
        desc : string
            The description from the config file
        """
        #Split at the first comma to get type, and value+description
        type,val_desc = value.split(',',1)
        #If it has a description, use it, otherwise, just use the config file key
        if len(val_desc.split(','))==2:
            val,desc_=val_desc.split(',')
            desc=desc_.strip()
        else:
            val=val_desc
            desc=name.strip()
            
        if type=='int':
            d=int(val)
        elif type=='float':
            d=float(val)
        elif type=='str':
            d=unicode(val)
        elif type=='State':
            Fluid,T,rho=val.split(',')
            d=dict(Fluid=Fluid,T=float(T),rho=float(rho))
        else:
            #Try to let the panel use the (name, value) directly
            if hasattr(self,'post_get_from_configfile'):
                d = self.post_get_from_configfile(name, value)
            else:
                raise KeyError('Type in line '+name+' = ' +value+' must be one of int,float,str')     
        return d, desc 
               
    def get_from_configfile(self, section, key = None, default = False):
        """
        This function will get parameters from the config file
        
        Parameters
        ----------
        section : string
            The section of the config file to retrieve values from
        key : string, optional
            The key of the value to return
        default : boolean, optional
            If ``True``, ALWAYS use the default config file
        
        Notes
        -----
        If section and key are provided, it will return just the value, either from
        the main config file if found or the default config file if not found.  
        If the parameter default is ``True``, it will ALWAYS use the default config file 
        
        Each of the values in the configuration 
        file may have a string in the format 
        
        int,3,
        float,3.0
        string,hello
        
        so that the code can know what type the value is.  If the value is something else,
        ask post_get_from_configfile if it knows what to do with it
        
        """
        d, desc={}, {}
        
        Main = wx.GetTopLevelParent(self)
        parser, default_parser = Main.get_config_objects()
        
        #Section not included, use the default section from the default config file
        if not parser.has_section(section):
            dlg = wx.MessageDialog(None,'Section '+section+' was not found, falling back to default configuration file')
            dlg.ShowModal()
            dlg.Destroy()
            _parser = default_parser
        elif default:
            # We are programmatically using the default parameters, 
            # don't warn'
            _parser = default_parser
        else:
            _parser = parser
        
        if key is not None:
            if default:
                #Use the default value
                value = default_parser.get(section, key)
                d[key],desc[key] =  self._get_from_configfile(key, value)
                return d,desc
            
            #Return the value from the file directly if the key is found
            elif _parser.has_option(section,key):
                value = _parser.get(section, key)
                _d,_desc =  self._get_from_configfile(key, value)
                return _d,_desc
            
            else:
                #Fall back to the default file
                warnings.warn('Did not find the key ['+key+'] in section '+section+', falling back to default config' )
                value = default_parser.get(section, key)
                _d,_desc =  self._get_from_configfile(key, value)
                return _d,_desc
        
        for name, value in _parser.items(section):
            d[name], desc[name] = self._get_from_configfile(name,value)
            
        return d,desc
    
    def get_additional_parametric_terms(self):
        """
        Provide additional parametric terms to the parametric table builder
        
        This function, when implemented in the derived class, will provide 
        additional terms to the parametric table builder.  If unimplemented, will
        just return ``None``.
        
        The format of the returned list should be a list of dictionaries with
        the terms:
            
            parent : a reference to this panel
            attr : the attribute in the simulation that will be linked with this term
            text : the label for the term
            
        Notes
        -----
        ``attr`` need not be actually the term that will ultimately be set in the simulation model
        
        It will be parsed by the apply_additional_parametric_term() function 
        below
        """
        pass
    
    def apply_additional_parametric_terms(self, attrs, vals, items):
        """
        
        Returns
        -------
        list of items that were unmatched
        
        Raises
        ------
        """
        return attrs, vals
    
    def BindChangeUnits(self, TextCtrl):
        self.Bind(wx.EVT_KEY_DOWN, self.OnChangeUnits, TextCtrl)
        
    def OnChangeUnits(self, event):
        TextCtrl = event.GetEventObject()
        dlg = UnitConvertor(value = float(TextCtrl.GetValue()),
                            default_units = TextCtrl.default_units
                            )
        
        dlg.ShowModal()
        TextCtrl.SetValue(dlg.get_value())
        dlg.Destroy()
        
class OutputTreePanel(wx.Panel):
    
    def __init__(self, parent, runs):
        
        import wx, textwrap
        import wx.gizmos
        from operator import mul
        
        wx.Panel.__init__(self, parent, -1)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        
        self.tree = wx.gizmos.TreeListCtrl(self, -1, style =
                                           wx.TR_DEFAULT_STYLE
                                           #| wx.TR_HAS_BUTTONS
                                           #| wx.TR_TWIST_BUTTONS
                                           #| wx.TR_ROW_LINES
                                           #| wx.TR_COLUMN_LINES
                                           #| wx.TR_NO_LINES 
                                           | wx.TR_FULL_ROW_HIGHLIGHT
                                           )

        isz = (16, 16)
        il = wx.ImageList(*isz)
        fldridx     = il.Add(wx.ArtProvider_GetBitmap(wx.ART_FOLDER,      wx.ART_OTHER, isz))
        fldropenidx = il.Add(wx.ArtProvider_GetBitmap(wx.ART_FILE_OPEN,   wx.ART_OTHER, isz))
        fileidx     = il.Add(wx.ArtProvider_GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, isz))

        self.tree.SetImageList(il)
        self.il = il
        self.tree.AddColumn("Main column")
        self.tree.SetMainColumn(0) # the one with the tree in it...
        self.tree.SetColumnWidth(0, 175)
        
        # Flush everything
        
        # Build the columns
        for i, run in enumerate(runs):
            self.tree.AddColumn("Run {i:d}".format(i = i))  

        # Create some columns
        self.root = self.tree.AddRoot("The Root Item")
        self.tree.SetItemImage(self.root, fldridx, which = wx.TreeItemIcon_Normal)
        self.tree.SetItemImage(self.root, fldropenidx, which = wx.TreeItemIcon_Expanded)
        
        # Make a list of list of keys for each HDF5 file
        lists_of_keys = []
        for run in runs:
            keys = []
            run.visit(keys.append) #For each thing in HDF5 file, append its name to the keys list
            lists_of_keys.append(keys)
        
        from time import clock
        t1 = clock()
        
        mylist = []
        def func(name, obj):
            if isinstance(obj, h5py.Dataset):
                try:
                    mylist.append((name, obj.value))
                except ValueError:
                    pass
            elif isinstance(obj, h5py.Group):
                mylist.append((name, None))
            else:
                return
                
        run.visititems(func)
        
        
        for el in mylist:
            r,v = el
            
            # Always make this level
            child = self.tree.AppendItem(self.root, r)
            self.tree.SetItemImage(child, fldridx, which = wx.TreeItemIcon_Normal)
            self.tree.SetItemImage(child, fldropenidx, which = wx.TreeItemIcon_Expanded)
            self.tree.SetItemText(child, str(v), 1)
            
        t2 = clock()
        print t2 - t1, 'to get all the items'
            
        self.runs = runs
        
        def _recursive_hdf5_add(root, objects):
            for thing in objects[0]:
                # Always make this level
                child = self.tree.AppendItem(root, str(thing))
                
                # If it is a dataset, write the dataset contents to the tree
                if isinstance(objects[0][thing], h5py.Dataset):
                    for i, o in enumerate(objects):
                        if not o[thing].shape: # It's a single element, perhaps a number or a string.  
                                               # shape will be an empty tuple, hence not () is True
                            self.tree.SetItemText(child, str(o[thing].value), i+1)
                        else:
                            # A place holder for now - will develop a frame to display the matrix
                            self.tree.SetItemText(child, str(o[thing]), i+1)
                
                # Otherwise if it is a group, change the icon and recurse into the group
                elif isinstance(objects[0][thing], h5py.Group):
                    
                    self.tree.SetItemImage(child, fldridx, which = wx.TreeItemIcon_Normal)
                    self.tree.SetItemImage(child, fldropenidx, which = wx.TreeItemIcon_Expanded)
                    _recursive_hdf5_add(child, [o[thing] for o in objects])
        

#        t1 = clock()
#        _recursive_hdf5_add(self.root, runs)
#        t2 = clock()
        
#        print t2-t1,'secs elapsed to load output tree'
        
        self.tree.Expand(self.root)

        self.tree.GetMainWindow().Bind(wx.EVT_RIGHT_UP, self.OnRightUp)
        self.tree.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.OnActivate)

    def OnActivate(self, evt):
        print('OnActivate: %s' % self.tree.GetItemText(evt.GetItem()))

    def OnRightUp(self, evt):
        pos = evt.GetPosition()
        item, flags, col = self.tree.HitTest(pos)
        if item:
            print('Flags: %s, Col:%s, Text: %s' %
                           (flags, col, self.tree.GetItemText(item, col)))

    def OnSize(self, evt):
        self.tree.SetSize(self.GetSize())
        
        
        
class ChangeParamsDialog(wx.Dialog):
    def __init__(self, params, **kwargs):
        wx.Dialog.__init__(self, None, **kwargs)
    
        self.params = params
        sizer = wx.FlexGridSizer(cols = 2)
        self.labels = []
        self.values = []
        self.attrs = []
    
        for p in self.params:
            l, v = LabeledItem(self,
                               label = p['desc'],
                               value = str(p['value'])
                               )
            self.labels.append(l)
            self.values.append(v)
            self.attrs.append(p['attr'])
            
            sizer.AddMany([l,v])
            
        self.SetSizer(sizer)
        min_width = min([l.GetSize()[0] for l in self.labels])
        for l in self.labels:
            l.SetMinSize((min_width,-1))
        sizer.Layout()
        self.Fit()
        
         #Bind a key-press event to all objects to get Esc 
        children = self.GetChildren()
        for child in children:
            child.Bind(wx.EVT_KEY_UP,  self.OnKeyPress)
    
    def get_values(self):
        params = []
        for l,v,k in zip(self.labels, self.values, self.attrs):
            params += [dict(desc = l.GetLabel(),
                           attr = k,
                           value = float(v.GetValue())
                        )]
        return params
            
    def OnAccept(self, event = None):
        self.EndModal(wx.ID_OK)
        
    def OnKeyPress(self,event = None):
        """ cancel if Escape key is pressed or accept if Enter """
        event.Skip()
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        elif event.GetKeyCode() == wx.WXK_RETURN:
            self.EndModal(wx.ID_OK)
    
    def CancelValues(self, event = None):
        self.EndModal(wx.ID_CANCEL)
        

class MassFlowOptionPanel(wx.Panel):
    """
    A wx.Panel for selecting the flow model and associated parameters
    
    Should not be instantiated directly, rather subclassed in order to provide the list of dictionaries
    of flow models for a given type of machine
    """
    def __init__(self,
                 parent,
                 key1, 
                 key2,
                 label = 'NONE',
                 types = None,
                 ):
        
        wx.Panel.__init__(self, parent)
        
        self.key1 = key1
        self.key2 = key2
        
        #Build the panel
        self.label = wx.StaticText(self, label=label)
        self.flowmodel_choices = wx.Choice(self)
        
        #Get the options from the derived class and store in a list
        self.options_list = self.model_options()
        
        #Load up the choicebox with the possible flow models possible
        for option in self.options_list:
            self.flowmodel_choices.Append(option['desc'])
        self.flowmodel_choices.SetSelection(0)
        
        #A button to fire the chooser
        self.params_button = wx.Button(self, label='Params...')
        
        for option in self.options_list:
            
            if option['desc'] == self.flowmodel_choices.GetStringSelection():
                
                #If parameters not provided (or not needed), disable the button
                if not 'params' in option or not option['params']:
                    self.params_button.Enable(False)
                else:
                    self.params_dict = option['params']
                    self.update_tooltip()            
                    self.params_button.Bind(wx.EVT_BUTTON, self.OnChangeParams)
                    
                TTS = self.dict_to_tooltip_string(option['params'])
                self.params_button.SetToolTipString(TTS)
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.label)
        sizer.Add(self.flowmodel_choices)
        sizer.Add(self.params_button)
        self.SetSizer(sizer)
        sizer.Layout()
        
    def model_options(self):
        """
        This function should return a list of dictionaries.  
        In each dictionary, the following terms must be defined:
        
        * desc : string
            Very terse description of the term 
        * function_name : function
            the function in the main machine class to be called
        * params : list of dictionaries with the keys 'attr', 'value', 'desc'
        
        MUST be implemented in the sub-class
        """
        raise NotImplementedError
    
    def update_tooltip(self):
        for option in self.options_list:
            if option['desc'] == self.flowmodel_choices.GetStringSelection():
                TTS = self.dict_to_tooltip_string(self.params_dict)
                self.params_button.SetToolTipString(TTS)
        
    def OnChangeParams(self, event):
        """
        Open a dialog to change the values
        """
        dlg = ChangeParamsDialog(self.params_dict)
        if dlg.ShowModal() == wx.ID_OK:
            self.params_dict = dlg.get_values()
            self.update_tooltip()
        dlg.Destroy()
        
    def dict_to_tooltip_string(self, params):
        """
        Take the dictionary of terms and turn it into a nice string for use in the
        tooltip of the textbox
        
        """
        
        s = ''
        for param in params:
            s += param['desc'] + ': ' + str(param['value']) + '\n'
        return s
    
    def get_function_name(self):
        for option in self.options_list:
            if option['desc'] == self.flowmodel_choices.GetStringSelection():
                return option['function_name']
        raise AttributeError
    
    def set_attr(self, attr, value):
        """
        Set an attribute in the params list of dictionaries
        
        Parameters
        ----------
        attr : string
            Attribute to be set
        value : 
            The value to be given to this attribute
        """
        
        #self.options_list is a list of dictionaries with the keys 'desc','function_name','params'
        for option in self.options_list:
            #Each param is a dictionary with keys of 'attr', 'value', 'desc'
            for param in option['params']:
                if param['attr'] == attr:
                    param['value'] = value
                    self.update_tooltip()
                    return
                
        raise KeyError('Did not find the attribute '+attr)
        
class ParaSelectDialog(wx.Dialog):
    def __init__(self):
        wx.Dialog.__init__(self, None, title = "State Chooser",)
        self.MinLabel, self.Min = LabeledItem(self, label = 'Minimum value', value = '')
        self.MaxLabel, self.Max = LabeledItem(self, label = 'Maximum value', value = '')
        self.StepsLabel, self.Steps = LabeledItem(self, label = 'Number of steps', value = '')
        self.Accept = wx.Button(self, label = "Accept")
        sizer = wx.FlexGridSizer(cols = 2, hgap = 4, vgap = 4)
        sizer.AddMany([self.MinLabel, self.Min, self.MaxLabel, 
                       self.Max, self.StepsLabel, self.Steps, self.Accept])
        self.SetSizer(sizer)
        sizer.Layout()
        self.Fit()
        self.Accept.Bind(wx.EVT_BUTTON, self.OnAccept)
        
        #Bind a key-press event to all objects to get Esc 
        children = self.GetChildren()
        for child in children:
            child.Bind(wx.EVT_KEY_UP,  self.OnKeyPress)
        
    def join_values(self):
        values = np.linspace(float(self.Min.GetValue()),float(self.Max.GetValue()),int(self.Steps.GetValue()))
        return ', '.join([str(val) for val in values]) 
        
    def OnAccept(self, event = None):
        self.EndModal(wx.ID_OK)
        
    def OnKeyPress(self,event = None):
        """ cancel if Escape key is pressed """
        event.Skip()
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
    
    def CancelValues(self, event = None):
        self.EndModal(wx.ID_CANCEL)


class ParametricOption(wx.Panel):
    def __init__(self, parent, GUI_objects):
        wx.Panel.__init__(self, parent)
        
        labels = [o.annotation for o in GUI_objects.itervalues()]
        
        # Check that there is no duplication between annotations
        if not len(labels) == len(set(labels)): # Sets do not allow duplication
            raise ValueError('You have duplicated annotations which is not allowed')
        
        # Make a reverse map from annotation to GUI object key
        self.GUI_map = {o.annotation:o.key for o in GUI_objects.itervalues()} 
        
        self.Terms = wx.ComboBox(self)
        self.Terms.AppendItems(labels)
        self.Terms.SetSelection(0)
        self.Terms.SetEditable(False)
        self.RemoveButton = wx.Button(self, label = '-', style = wx.ID_REMOVE)
        
        self.Values = wx.TextCtrl(self, value = '')
        self.Select = wx.Button(self, label = 'Select...')
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.RemoveButton)
        sizer.Add(self.Terms)
        sizer.Add(self.Values)
        sizer.Add(self.Select)
        self.SetSizer(sizer)
        
        self.Select.Bind(wx.EVT_BUTTON,self.OnSelectValues)
        self.RemoveButton.Bind(wx.EVT_BUTTON, lambda event: self.Parent.RemoveTerm(self))
        self.Terms.Bind(wx.EVT_COMBOBOX, self.OnChangeTerm)
        
        self.OnChangeTerm()
        
    def OnChangeTerm(self, event = None):
        """
        Update the values when the term is changed if a structured table
        """
        if self.GetParent().Structured.GetValue():
            annotation = self.Terms.GetStringSelection()
            
            # Get the key of the registered object
            key = self.GUI_map[annotation]
            
            # Get the value of the item in the GUI
            val = self.GetTopLevelParent().get_GUI_object_value(key)
            
            # Set the textctrl with this value
            self.Values.SetValue(str(val))
    
    def OnSelectValues(self, event = None):
        dlg = ParaSelectDialog()
        if dlg.ShowModal() == wx.ID_OK:
            self.Values.SetValue(dlg.join_values())
        dlg.Destroy()
        
    def get_values(self):
        """
        Get a list of floats from the items in the textbox
        """
        name = self.Terms.GetStringSelection()
        #To list of floats
        if hasattr(self,'Values'):
            values = [float(val) for val in self.Values.GetValue().split(',') if not val == '']
        else:
            values = None
        return name, values
    
    def set_values(self,key,value):
        self.Terms.SetStringSelection(key)
        self.Values.SetValue(value)
        
    def update_parametric_terms(self, items):
        """
        Update the items in each of the comboboxes
        """
        labels = [item['text'] for item in items]
        #Get the old string
        old_val = self.Terms.GetStringSelection()
        #Update the contents of the combobox
        self.Terms.SetItems(labels)
        #Reset the string
        self.Terms.SetStringSelection(old_val)
        
    def make_unstructured(self):
        if hasattr(self,'Values'):
            self.Values.Destroy()
            del self.Values
        if hasattr(self,'Select'):
            self.Select.Destroy()
            del self.Select
            
        self.GetSizer().Layout()
        self.Refresh()
    
    def make_structured(self):
        if not hasattr(self,'Values'):
            self.Values = wx.TextCtrl(self, value = '')
            self.Select = wx.Button(self, label = 'Select...')
            self.Select.Bind(wx.EVT_BUTTON,self.OnSelectValues)
            self.GetSizer().AddMany([self.Values,self.Select])
            self.GetSizer().Layout()
            self.Refresh()
            self.OnChangeTerm()
        
class ParametricCheckList(wx.ListCtrl, ListCtrlAutoWidthMixin, CheckListCtrlMixin, TextEditMixin):
    """
    The checklist that stores all the possible runs
    """
    def __init__(self, parent, headers, values, structured = True):
        """
        Parameters
        ----------
        parent : wx.window
            The parent of this checklist
        headers : list
            A list of header strings
        values : 
        structured : bool
            If ``True``, use a structured parametric table to do the calcs
        """
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT)
        ListCtrlAutoWidthMixin.__init__(self)
        CheckListCtrlMixin.__init__(self)
        TextEditMixin.__init__(self)
        
        #Build the headers
        self.InsertColumn(0, '')
        self.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        for i, header in enumerate(headers):
            self.InsertColumn(i+1, header)
        
        if not structured:
            #Transpose the nested lists
            self.data = zip(*values)
            #Turn back from tuples to lists
            self.data = [list(row) for row in self.data]
        else:
            self.data = [list(row) for row in itertools.product(*values)]
        
        #Add the values one row at a time
        for i,row in enumerate(self.data):
            self.InsertStringItem(i,'')
            for j,val in enumerate(row):
                self.SetStringItem(i,j+1,str(val))
            self.CheckItem(i)
            
        for i in range(len(headers)):
            self.SetColumnWidth(i+1,wx.LIST_AUTOSIZE_USEHEADER)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)
        self.Bind(wx.EVT_LIST_BEGIN_LABEL_EDIT, self.PreCellEdit)
        self.Bind(wx.EVT_LIST_END_LABEL_EDIT, self.OnCellEdited)

    def OnItemActivated(self, event):
        self.ToggleItem(event.m_itemIndex)
    
    def PreCellEdit(self, event):
        """
        Before the cell is edited, only allow edits on columns after the first one
        """
        row_index = event.m_itemIndex
        col_index = event.Column
        if col_index == 0:
            event.Veto()
        else:
            val = float(event.Text)
            self.data[row_index][col_index-1] = val
            event.Skip()
    
    def OnCellEdited(self, event):
        """
        Once the cell is edited, write its value back into the data matrix
        """
        row_index = event.m_itemIndex
        col_index = event.Column
        val = float(event.Text)
        self.data[row_index][col_index-1] = val
    
    def GetStringCell(self,Irow,Icol):
        """ Returns a string representation of the cell """
        return self.data[Irow][Icol]
    
    def GetFloatCell(self,Irow,Icol):
        """ Returns a float representation of the cell """
        return float(self.data[Irow][Icol])
    
    def AddRow(self):
        
        row = [0]*self.GetColumnCount()
        
        i = len(self.data)-1
        self.InsertStringItem(i,'')
        for j,val in enumerate(row):
            self.SetStringItem(i,j+1,str(val))
        self.CheckItem(i)
        
        self.data.append(row)
        
    def RemoveRow(self, i = 0):
        self.data.pop(i)
        self.DeleteItem(i)
        
    def RemoveLastRow(self):
        i = len(self.data)-1
        self.data.pop(i)
        self.DeleteItem(i)
                               
class HackedButton(wx.Button):
    """
    This is needed because of a bug in FlatMenu where clicking on a disabled 
    item throws an exception
    """
    def __init__(self, parent, *args, **kwargs):
        wx.Button.__init__(self, parent, *args, **kwargs)
        
        self.Enable()
        
    def Enable(self):
        self.SetForegroundColour((50,50,50))
        self._Enabled = True
        self.SetEvtHandlerEnabled(True)
        
    def Disable(self):
        self.SetForegroundColour((255,255,255))
        self._Enabled = False
        self.SetEvtHandlerEnabled(False)
         
class ParametricPanel(PDPanel):
    def __init__(self, parent, configdict, **kwargs):
        PDPanel.__init__(self, parent, **kwargs)
        
        import wx.lib.agw.flatmenu as FM
        from wx.lib.agw.fmresources import FM_OPT_SHOW_CUSTOMIZE, FM_OPT_SHOW_TOOLBAR, FM_OPT_MINIBAR
        self._mb = FM.FlatMenuBar(self, wx.ID_ANY, 10, 5, options = FM_OPT_SHOW_TOOLBAR)
        
        self.Structured = wx.CheckBox(self._mb, label = 'Structured')
        self._mb.AddControl(self.Structured)
        self.Structured.Bind(wx.EVT_CHECKBOX, self.OnChangeStructured)
        self.Structured.SetValue(1)
        
        self.AddButton = HackedButton(self._mb, label = 'Add Term')
        self._mb.AddControl(self.AddButton)
        self.AddButton.Bind(wx.EVT_BUTTON, self.OnAddTerm)
        
        self.BuildButton = HackedButton(self._mb, label = 'Build Table')
        self._mb.AddControl(self.BuildButton)
        self.BuildButton.Bind(wx.EVT_BUTTON, self.OnBuildTable)
        self.BuildButton.Disable()
        
        self.RunButton = HackedButton(self._mb, label = 'Run Table')
        self._mb.AddControl(self.RunButton)
        self.RunButton.Bind(wx.EVT_BUTTON, self.OnRunTable)
        self.RunButton.Disable()
        
        self.ZipButton = HackedButton(self._mb, label = 'Make Batch .zip')
        self._mb.AddControl(self.ZipButton)
        self.ZipButton.Bind(wx.EVT_BUTTON, self.OnZipBatch)
        self.ZipButton.Disable()
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._mb,0,wx.EXPAND)
        self.SetSizer(sizer)
        sizer.Layout()
        
        self.NTerms = 0
        self.ParamSizer = None
        self.ParamListSizer = None
        self.ParaList = None
        
        self.GUI_map = {o.annotation:o.key for o in self.main.get_GUI_object_dict().itervalues()} 
        
        # After all the building is done, check if it is unstructured, if so, 
        # collect the temporary values that were set 
#        if self.Structured.GetValue() == True:
#            self.OnBuildTable()
        self.Layout()
        self.OnChangeStructured()
            
    def OnChangeStructured(self, event = None):
        
        #Param
        terms = [term for term in self.Children if isinstance(term,ParametricOption)]
        
        for term in terms:
            if self.Structured.GetValue() == True:
                term.make_structured()
            else:
                term.make_unstructured()

        self.GetSizer().Layout()
        self.Refresh()
            
    def OnAddTerm(self, event = None):
        if self.NTerms == 0:
            self.ParamSizerBox = wx.StaticBox(self, label = "Parametric Terms")
            self.ParamSizer = wx.StaticBoxSizer(self.ParamSizerBox, wx.VERTICAL)
            self.GetSizer().Add(self.ParamSizer)
            self.BuildButton.Enable()
        # Get all the registered GUI objects
        GUI_objects = self.main.get_GUI_object_dict()
        # Create the option panel
        option = ParametricOption(self, GUI_objects)
        # Make it either structured or unstructured
        if self.Structured.GetValue() == True:
            option.make_structured()
        else:
            option.make_unstructured()
        
        self.ParamSizer.Add(option)
        self.ParamSizer.Layout()
        self.NTerms += 1
        self.GetSizer().Layout()
        self.Refresh()
    
    def RemoveTerm(self, term):
        term.Destroy()
        self.NTerms -= 1
        if self.NTerms == 0:
            if self.ParamSizer is not None:
                self.GetSizer().Remove(self.ParamSizer)
                self.ParamSizer = None
            if self.ParaList is not None:
                self.ParaList.Destroy()
                self.ParaList = None
            if self.ParamListSizer is not None:
                self.GetSizer().Remove(self.ParamListSizer)
                self.ParamListSizer = None
            self.RunButton.Disable()
            self.BuildButton.Disable()
            self.ZipButton.Disable()
        else:
            self.ParamSizer.Layout()
        self.GetSizer().Layout()
        self.Refresh()
        
    def OnBuildTable(self, event=None):
        names = []
        values = []
        #make names a list of strings
        #make values a list of lists of values
        for param in self.ParamSizer.GetChildren():
            name, vals = param.Window.get_values()
            names.append(name)
            if self.Structured.GetValue() == True:
                values.append(vals)
            else:
                if hasattr(param.Window,'temporary_values'):
                    values.append(param.Window.temporary_values.split(';'))
                else:
                    values.append(['0.0'])
        
        #Build the list of parameters for the parametric study
        if self.ParamListSizer is None:
            self.ParamListBox = wx.StaticBox(self, label = "Parametric Terms Ranges")
            self.ParamListSizer = wx.StaticBoxSizer(self.ParamListBox, wx.VERTICAL)
        else:
            self.ParaList.Destroy()
            self.GetSizer().Remove(self.ParamListSizer)
#            #Build and add a sizer for the para values
            self.ParamListBox = wx.StaticBox(self, label = "Parametric Runs")
            self.ParamListSizer = wx.StaticBoxSizer(self.ParamListBox, wx.VERTICAL)
        
        #Remove the spinner and its friends
        if hasattr(self,'RowCountSpinner'):
            self.RowCountSpinner.Destroy(); del self.RowCountSpinner
            self.RowCountLabel.Destroy(); del self.RowCountLabel
            self.RowCountSpinnerText.Destroy(); del self.RowCountSpinnerText
            
        #Build and add a sizer for the para values
        if self.Structured.GetValue() == False:
            self.RowCountLabel = wx.StaticText(self,label='Number of rows')
            self.RowCountSpinnerText = wx.TextCtrl(self, value = "1", size = (40,-1))
            h = self.RowCountSpinnerText.GetSize().height
            w = self.RowCountSpinnerText.GetSize().width + self.RowCountSpinnerText.GetPosition().x + 2
            self.RowCountSpinner = wx.SpinButton(self, wx.ID_ANY, (w,50), (h*2/3,h), style = wx.SP_VERTICAL)
            self.RowCountSpinner.SetRange(1, 100)
            self.RowCountSpinner.SetValue(1)
            self.RowCountSpinner.Bind(wx.EVT_SPIN_UP, self.OnSpinUp)
            self.RowCountSpinner.Bind(wx.EVT_SPIN_DOWN, self.OnSpinDown)
            
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.AddMany([self.RowCountLabel, self.RowCountSpinner,self.RowCountSpinnerText])
            self.GetSizer().Add(sizer)
                    
        self.GetSizer().Add(self.ParamListSizer,1,wx.EXPAND)
        self.ParaList = ParametricCheckList(self,names,values,
                                            structured = self.Structured.GetValue())
            
        self.ParamListSizer.Add(self.ParaList,1,wx.EXPAND)
        self.ParaList.SetMinSize((400,-1))
        self.ParamListSizer.Layout()
        self.GetSizer().Layout()
        self.Refresh() 
        
        # Enable the batch buttons
        self.RunButton.Enable()
        self.ZipButton.Enable()
            
        if self.Structured.GetValue() == False:
            self.RowCountSpinner.SetValue(self.ParaList.GetItemCount())
            self.RowCountSpinnerText.SetValue(str(self.ParaList.GetItemCount()))
            #Bind a right click to opening a popup
            # for wxMSW
            self.ParaList.Bind(wx.EVT_COMMAND_RIGHT_CLICK, self.OnParaListRightClick)
            # for wxGTK
            self.ParaList.Bind(wx.EVT_RIGHT_UP, self.OnParaListRightClick)
            
    def OnParaListRightClick(self, event): 
        #based on wxpython demo program
        
        # make a menu
        menu = wx.Menu()
        # add some items
        menuitem1 = wx.MenuItem(menu, -1, 'Fill from clipboard')
        menuitem2 = wx.MenuItem(menu, -1, 'Fill from csv file (future)')
        
        self.Bind(wx.EVT_MENU, self.OnPaste, menuitem1)
        menu.AppendItem(menuitem1)
        menu.AppendItem(menuitem2)
        
        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        self.PopupMenu(menu)
        menu.Destroy()
        
    def OnPaste(self, event):
        """
        Paste the contents of the clipboard into the table
        """
        do = wx.TextDataObject()
        if wx.TheClipboard.Open():
            success = wx.TheClipboard.GetData(do)
            wx.TheClipboard.Close()

        data = do.GetText()
        rows = data.strip().replace('\r','').split('\n')
        rows = [row.split('\t') for row in rows]
        #Check that the dimensions of pasted section and table are the same
        if not self.ParaList.GetItemCount() == len(rows):
            msg = 'There are '+str(len(rows))+' rows in your pasted table, but '+str(self.ParaList.GetItemCount())+' rows in the table'
            dlg = wx.MessageDialog(None, msg)
            dlg.ShowModal()
            dlg.Destroy()
            return
        else:
            #Right number of rows, set the values
            for i,row in enumerate(rows): 
                for j,item in enumerate(row): 
                    self.ParaList.SetStringItem(i,j+1,item)
                    self.ParaList.data[i][j] = item
        
    def OnSpinDown(self, event):
        """ 
        Fires when the spinner is used to decrease the number of rows
        """
        
        if event.GetPosition()>=1:
            
            # Set the textbox value
            self.RowCountSpinnerText.SetValue(str(event.GetPosition()))
        
            #Remove the last row
            self.ParaList.RemoveLastRow()
        
        
    def OnSpinUp(self, event):
        """ 
        Fires when the spinner is used to increase the number of rows
        """
        #Set the textbox value
        self.RowCountSpinnerText.SetValue(str(event.GetPosition()))
        
        #Add a row
        self.ParaList.AddRow()
        
    def build_all_scripts(self):
        sims = []
        
        # Get a copy of the dictionary of all the registered terms
        # 
        
        # Column index 1 is the list of parameters
        for Irow in range(self.ParaList.GetItemCount()):
            # Loop over all the rows that are checked
            if self.ParaList.IsChecked(Irow):
                
                #Empty lists for this run
                vals, names = [], []
                
                # Each row corresponds to one run of the model
                # 
                # Loop over the columns for this row 
                for Icol in range(self.ParaList.GetColumnCount()-1):
                    vals.append(self.ParaList.GetFloatCell(Irow, Icol))
                    names.append(self.ParaList.GetColumn(Icol+1).Text)
                    
                # The attributes corresponding to the names
                keys = [self.GUI_map[name] for name in names]
                
                # Set the value in the GUI
                for key,val in zip(keys,vals):
                    self.main.set_GUI_object_value(key, val)
                
                #Build the simulation script using the GUI parameters
                script_name = self.main.build_simulation_script()
                            
                #Add sim to the list (actually append the path to the script)
                sims.append(script_name)
                
        # Check that there is a difference between the files generated 
        if not self.check_scripts_are_different(sims):
            dlg = wx.MessageDialog(None,'Cannot run batch because some of the batch files are exactly the same. Deleting generated scripts')
            dlg.ShowModal()
            dlg.Destroy()
            
            for file in sims:
                # Full path to file
                fName = os.path.join(PDSimGUI.pdsim_home_folder,file)
                # Remove the file generated, don't do anything if error
                try:
                    os.unlink(fName)
                except OSError:
                    pass
            
            return []
        
        return sims
        
    def OnRunTable(self, event=None):
        """
        Actually runs the parametric table
        
        This event can only fire if the table is built
        """
        
        #Build all the scripts
        sims = self.build_all_scripts()
        
        if sims:
            #Actually run the batch with the sims that have been built
            self.main.run_batch(sims)
        
    def check_scripts_are_different(self, scripts):
        """
        return ``True`` if the scripts differ by more than the time stamp, ``False`` otherwise
        
        The first 10 lines are not considered in the diff
        """
        
        # Take the lines that follow the first 10 lines
        chopped_scripts = [open(os.path.join(PDSimGUI.pdsim_home_folder,fName),'r').readlines()[10::] for fName in scripts]
        
        for i in range(len(chopped_scripts)):
            for j in range(i+1,len(chopped_scripts)):
                # If the list of unified diffs is empty, the files are the same
                # This is a failure
                if not [d for d in difflib.unified_diff(chopped_scripts[i],chopped_scripts[j])]:
                    return False
        # sMade it this far, return True, all the files are different
        return True
        
    def OnZipBatch(self, event = None):
        
        template = textwrap.dedent(
        """
        import glob, os
        from PDSim.misc.hdf5 import HDF5Writer
        
        H = HDF5Writer()
        
        for file in glob.glob('script_*.py'):
            root,ext = os.path.splitext(file)
            mod = __import__(root)
            sim = mod.build()
            mod.run(sim)
            
            #Remove FlowsStorage as it is enormous
            del sim.FlowStorage
            
            H.write_to_file(sim,root+'.h5')
               
           """
           )
        
        sims = self.build_all_scripts()
        
        if sims:
            
            FD = wx.FileDialog(None,
                               "Save zip file",
                               defaultDir='.',
                               wildcard =  "ZIP files (*.zip)|*.zip|All Files|*.*",
                               style = wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
            if wx.ID_OK==FD.ShowModal():
                zip_file_path = FD.GetPath()
            else:
                zip_file_path = ''
            FD.Destroy()
        
            if zip_file_path:
                with zipfile.ZipFile(zip_file_path,'w') as z:
                    for file in sims:
                        # Full path to file
                        fName = os.path.join(PDSimGUI.pdsim_home_folder,file)
                        # write the file, strip off the path
                        z.write(fName, arcname = file)
                    
                    z.writestr('run.py',template)
        
    def post_prep_for_configfile(self):
        """
        This panel's outputs for the save file
        """
        if not hasattr(self, 'ParaList'):
            return ''
        
        if self.Structured.GetStringSelection() == 'Structured':
            s = 'Structured = PPStructured, True\n'
            for i, param in enumerate(self.ParamSizer.GetChildren()):
                name, vals = param.Window.get_values()
                if vals is not None:
                    values = ';'.join([str(val) for val in vals])
                else:
                    values = ''
                s += 'Term' + str(i+1) + ' = Term,' + name +',' + values + '\n'
        else:
            s = 'Structured = PPStructured, False\n'
            for i, param in enumerate(self.ParamSizer.GetChildren()):
                name, _dummy = param.Window.get_values()
                values = ';'.join([str(row[i]) for row in self.ParaList.data])
                s += 'Term' + str(i+1) + ' = Term,' + name +',' + values + '\n' 
        return s
    
    def post_get_from_configfile(self, key, value):
        if not value.split(',')[0].startswith('Term'):
            if value.split(',')[0].strip() == 'PPStructured':
                if value.split(',')[1].strip() == 'True':
                    self.Structured.SetStringSelection('Structured')
                elif value.split(',')[1].strip() == 'False':
                    self.Structured.SetStringSelection('Unstructured')
                else:
                    raise KeyError
            return
        #value is something like "Term1,Piston diameter [m],0.02;0.025"
        string_, value = value.split(',')[1:3]
        #value = Piston diameter [m],0.02;0.025
        #Add a new entry to the table
        self.OnAddTerm()
        I = len(self.ParamSizer.GetChildren())-1
        if self.Structured.GetStringSelection() == 'Structured':
            #Load the values into the variables in the list of variables
            self.ParamSizer.GetItem(I).Window.set_values(string_,value.replace(';',', '))
        else:
            self.ParamSizer.GetItem(I).Window.Terms.SetStringSelection(string_)
            self.ParamSizer.GetItem(I).Window.temporary_values = value

def LabeledItem(parent,id=-1, label='A label', value='0.0', enabled=True, tooltip = None):
    """
    A convenience function that returns a tuple of StaticText and TextCtrl 
    items with the necessary label and values set
    """
    label = wx.StaticText(parent,id,label)
    thing = wx.TextCtrl(parent,id,value)
    if enabled==False:
        thing.Disable()
    if tooltip is not None:
        if enabled:
            thing.SetToolTipString(tooltip)
        else:
            label.SetToolTipString(tooltip)
    return label,thing

class StateChooser(wx.Dialog):
    """
    A dialog used to select the state
    """
    def __init__(self,Fluid,T,rho,parent=None,id=-1,Fluid_fixed = False):
        wx.Dialog.__init__(self,parent,id,"State Chooser",size=(300,250))
        
        class StateChoices(wx.Choicebook):
            def __init__(self, parent, id=-1,):
                wx.Choicebook.__init__(self, parent, id)
                
                self.pageT_dTsh=wx.Panel(self)
                self.AddPage(self.pageT_dTsh,'Saturation Temperature and Superheat')
                self.Tsatlabel1, self.Tsat1 = LabeledItem(self.pageT_dTsh,label="Saturation Temperature [K]",value='290')
                self.Tsat1.default_units = 'Kelvin'
                self.Tsat1.Bind(wx.EVT_CONTEXT_MENU,self.OnChangeUnits)
                self.DTshlabel1, self.DTsh1 = LabeledItem(self.pageT_dTsh,label="Superheat [K]",value='11.1')
                sizer=wx.FlexGridSizer(cols=2,hgap=3,vgap=3)
                sizer.AddMany([self.Tsatlabel1, self.Tsat1,self.DTshlabel1, self.DTsh1])
                self.pageT_dTsh.SetSizer(sizer)
                
                self.pageT_p=wx.Panel(self)
                self.AddPage(self.pageT_p,'Temperature and Absolute Pressure')
                self.Tlabel1, self.T1 = LabeledItem(self.pageT_p,label="Temperature [K]",value='300')
                self.T1.default_units = 'Kelvin'
                self.T1.Bind(wx.EVT_CONTEXT_MENU,self.OnChangeUnits)
                self.plabel1, self.p1 = LabeledItem(self.pageT_p,label="Pressure [kPa]",value='300')
                self.p1.default_units = 'kPa'
                self.p1.Bind(wx.EVT_CONTEXT_MENU,self.OnChangeUnits)
                sizer=wx.FlexGridSizer(cols=2,hgap=3,vgap=3)
                sizer.AddMany([self.Tlabel1, self.T1,self.plabel1, self.p1])
                self.pageT_p.SetSizer(sizer)
            
            def OnChangeUnits(self, event):
                TextCtrl = event.GetEventObject()
                dlg = UnitConvertor(value = float(TextCtrl.GetValue()),
                                    default_units = TextCtrl.default_units
                                    )
                dlg.ShowModal()
                TextCtrl.SetValue(dlg.get_value())
                dlg.Destroy()
        
        sizer=wx.BoxSizer(wx.VERTICAL)
        self.Fluidslabel = wx.StaticText(self,-1,'Fluid: ')
        self.Fluids = wx.ComboBox(self,-1)
        self.Fluids.AppendItems(sorted(CoolProp.__fluids__))
        self.Fluids.SetEditable(False)
        self.Fluids.SetValue(Fluid)
        if Fluid_fixed:
            self.Fluids.Enable(False)
        
        hs = wx.BoxSizer(wx.HORIZONTAL)
        hs.AddMany([self.Fluidslabel,self.Fluids])
        sizer.Add(hs)
        
        sizer.Add((5,5))
        
        self.SC=StateChoices(self)
        sizer.Add(self.SC,1,wx.EXPAND)                
        
        fgs= wx.FlexGridSizer(cols=2,hgap=3,vgap=3)
        self.Tlabel, self.T = LabeledItem(self,label="Temperature [K]",value='300',enabled=False)
        self.plabel, self.p = LabeledItem(self,label="Pressure [kPa]",value='300',enabled=False)
        self.rholabel, self.rho = LabeledItem(self,label="Density [kg/m�]",value='1',enabled=False)
        fgs.AddMany([self.Tlabel,self.T,self.plabel,self.p,self.rholabel,self.rho])
        sizer.Add(fgs)
        
        self.cmdAccept = wx.Button(self,-1,"Accept")
        sizer.Add(self.cmdAccept)
        
        self.SetSizer(sizer)
        self.Fluids.SetStringSelection(Fluid)
        
        if CP.Props(Fluid,"Ttriple") < T < CP.Props(Fluid,"Tcrit"):
            #Pressure from temperature and density
            p = CP.Props('P','T',T,'D',rho,Fluid)
            #Saturation temperature
            Tsat = CP.Props('T','P',p,'Q',1,Fluid)
            self.SC.Tsat1.SetValue(str(Tsat))
            self.SC.DTsh1.SetValue(str(T-Tsat))
            self.SC.T1.SetValue(str(T))
            self.SC.p1.SetValue(str(p))
            self.SC.SetSelection(0) ## The page of Tsat,DTsh
        else:
            #Pressure from temperature and density
            p = CP.Props('P','T',T,'D',rho,Fluid)
            self.SC.T1.SetValue(str(T))
            self.SC.p1.SetValue(str(p))
            self.SC.SetSelection(1) ## The page of Tsat,DTsh
        
        self.OnUpdateVals()
        
        self.SC.Tsat1.Bind(wx.EVT_KEY_UP,self.OnUpdateVals)
        self.SC.DTsh1.Bind(wx.EVT_KEY_UP,self.OnUpdateVals)
        self.SC.T1.Bind(wx.EVT_KEY_UP,self.OnUpdateVals)
        self.SC.p1.Bind(wx.EVT_KEY_UP,self.OnUpdateVals)
        
        self.Fluids.Bind(wx.EVT_COMBOBOX, self.OnFlushVals)
        self.Bind(wx.EVT_CLOSE,self.CancelValues)
        self.cmdAccept.Bind(wx.EVT_BUTTON,self.AcceptValues)
        
        #Bind a key-press event to all objects to get Esc 
        children = self.GetChildren()
        for child in children:
            child.Bind(wx.EVT_KEY_UP,  self.OnKeyPress)
        
    def OnFlushVals(self,event=None):
        """ Clear all the values"""
        self.SC.Tsat1.SetValue("")
        self.SC.DTsh1.SetValue("")
        self.SC.T1.SetValue("")
        self.SC.p1.SetValue("")
        self.T.SetValue("")
        self.p.SetValue("")
        self.rho.SetValue("")
        
    def OnKeyPress(self,event=None):
        """ cancel if Escape key is pressed """
        event.Skip()
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
    
    def CancelValues(self,event=None):
        self.EndModal(wx.ID_CANCEL)
        
    def AcceptValues(self,event=None):
        """ If the state is in the vapor phase somewhere, accept it and return """
        Fluid = str(self.Fluids.GetStringSelection())
        T=float(self.T.GetValue())
        p=float(self.p.GetValue())
        if CP.Phase(Fluid,T,p) not in ['Gas','Supercritical']:
            dlg = wx.MessageDialog(None, message = "The phase is not gas or supercritical, cannot accept this state",caption='Invalid state')
            dlg.ShowModal()
            dlg.Destroy()
            return
        self.EndModal(wx.ID_OK)
    
    def GetValues(self):
        Fluid=str(self.Fluids.GetStringSelection())
        T=float(self.T.GetValue())
        p=float(self.p.GetValue())
        rho=float(self.rho.GetValue())
        return Fluid,T,p,rho
        
    def OnUpdateVals(self,event=None):
        if event is not None:
            event.Skip()
            
        PageNum = self.SC.GetSelection()
        Fluid = str(self.Fluids.GetStringSelection())
        try:
            if PageNum == 0:
                #Sat temperature and superheat are given
                p=CP.Props('P','T',float(self.SC.Tsat1.GetValue()),'Q',1.0,Fluid)
                T=float(self.SC.Tsat1.GetValue())+float(self.SC.DTsh1.GetValue())
                rho=CP.Props('D','T',T,'P',p,Fluid)
            elif PageNum == 1:
                #Temperature and pressure are given
                T=float(self.SC.T1.GetValue())
                p=float(self.SC.p1.GetValue())
                rho=CP.Props('D','T',T,'P',p,Fluid)
            else:
                raise NotImplementedError
            
            self.T.SetValue(str(T))
            self.p.SetValue(str(p))
            self.rho.SetValue(str(rho))
        except ValueError:
            return
        
class StatePanel(wx.Panel):
    """
    This is a generic Panel that has the ability to select a state given by 
    Fluid, temperature and density by selecting the desired set of inputs in a
    dialog which can be Tsat and DTsh or T & p.
    """
    def __init__(self, parent, id=-1, CPState = None, Fluid_fixed = False):
        wx.Panel.__init__(self, parent, id)
        
        # If the fluid is not allowed to be changed Fluid_fixed is true
        self._Fluid_fixed = Fluid_fixed
        
        sizer = wx.FlexGridSizer(cols=2,hgap=4,vgap=4)
        self.Fluidlabel, self.Fluid = LabeledItem(self,label="Fluid",value=str(CPState.Fluid))
        
        self.Tlabel, self.T = LabeledItem(self,label="Temperature [K]",value=str(CPState.T))
        self.plabel, self.p = LabeledItem(self,label="Pressure [kPa]",value=str(CPState.p))
        self.rholabel, self.rho = LabeledItem(self,label="Density [kg/m�]",value=str(CPState.rho))
        sizer.AddMany([self.Fluidlabel, self.Fluid,
                       self.Tlabel, self.T,
                       self.plabel, self.p,
                       self.rholabel, self.rho])
        
        for box in [self.T,self.p,self.rho,self.Fluid]:
            #Make the box not editable
            self.Fluid.SetEditable(False)
            #Bind events tp fire the chooser when text boxes are clicked on
            box.Bind(wx.EVT_LEFT_DOWN,self.UseChooser)
            box.SetToolTipString('Click on me to select the state')
        
        self.SetSizer(sizer)
        
        # create event class so that you can fire an event for when the state is changed
        # Other panels can await this event and do something when it happens
        import wx.lib.newevent as newevent
        self.StateUpdateEvent, self.EVT_STATE_UPDATE_EVENT = newevent.NewEvent()
        
    def GetState(self):
        """
        returns a :class:`CoolProp.State.State` instance from the given values
        in the panel
        """
        Fluid = str(self.Fluid.GetValue())
        T = float(self.T.GetValue())
        rho = float(self.rho.GetValue())
        return State(Fluid,dict(T = T, D = rho))
    
    def GetValue(self):
        return self.GetState()
    
    def SetValue(self, State_val):
        self.set_state(State_val.Fluid, dict(T= State_val.T, D = State_val.rho))
    
    def set_state(self, Fluid, **kwargs):
        """
        Fluid must not be unicode
        """
        if self._Fluid_fixed and not str(self.Fluid.GetValue()) == str(Fluid):
            import warnings
            warnings.warn('Could not set state since fluid is fixed')
            return

        #Create a state instance from the parameters passed in
        S  = State(str(Fluid), kwargs)

        #Load up the textboxes
        self.Fluid.SetValue(S.Fluid)
        self.T.SetValue(str(S.T))
        self.rho.SetValue(str(S.rho))
        self.p.SetValue(str(S.p))
    
    def UseChooser(self,event=None):
        """
        An event handler that runs the State Chooser dialog and sets the
        values back in the panel
        """
        #Values from the GUI
        Fluid = str(self.Fluid.GetValue())
        T = float(self.T.GetValue())
        rho = float(self.rho.GetValue())
        
        #Instantiate the chooser Dialog
        SCfrm=StateChooser(Fluid=Fluid,T=T,rho=rho,Fluid_fixed = self._Fluid_fixed)
        
        #If they clicked accept
        if wx.ID_OK == SCfrm.ShowModal():
            Fluid,T,p,rho=SCfrm.GetValues()
            #Set the GUI values
            self.Fluid.SetValue(str(Fluid))
            self.T.SetValue(str(T))
            self.p.SetValue(str(p))
            self.rho.SetValue(str(rho))
        SCfrm.Destroy()
        
        # post the update event, with arbitrary data attached
        wx.PostEvent(self, self.StateUpdateEvent())

class StateInputsPanel(PDPanel):
    
    desc_map = dict(omega = ('Rotational speed [rad/s]','rad/s'),
                    inletState = ('The inlet state to the machine','-'),
                    discPratio = ('Pressure ratio (disc/suction)','-'),
                    discPressure = ('Discharge pressure [kPa]','kPa'),
                    discTsat = ('Discharge saturation temperature [K]','K'),
                    )
    
    def __init__(self, parent, config, **kwargs):
    
        PDPanel.__init__(self, parent, **kwargs)
        
        # The CoolProp State instance
        inletState = State(config['inletState']['Fluid'], dict(T = config['inletState']['T'], D = config['inletState']['rho']))
        
        # Create the sizers
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_for_omega = wx.BoxSizer(wx.HORIZONTAL)
        sizer_for_inletState = wx.BoxSizer(wx.HORIZONTAL)
        sizer_for_discState = wx.FlexGridSizer(cols = 2)
        
        # The list for all the annotated objects
        self.annotated_values = []
        
        # Add the annotated omega to the list of objects
        self.annotated_values.append(AnnotatedValue('omega', config['omega'], *self.desc_map['omega'])) #*self.desc_map[key] unpacks into annotation, units
        
        # Construct annotated omega GUI entry
        AGO_omega = self.construct_items(self.annotated_values, sizer_for_omega)
        AGO_omega.GUI_location.SetToolTipString('If a motor curve is provided, this value will not be used')
        
        # Construct StatePanel
        self.SuctionStatePanel = StatePanel(self, CPState = inletState)
        AGO_inletState = AnnotatedGUIObject(AnnotatedValue('inletState', inletState, *self.desc_map['inletState']), self.SuctionStatePanel)
        
        #Construct the discharge state
        if 'pratio' in config['discharge']:
            pratio = config['discharge']['pratio']
            pressure = pratio * inletState.p
            Tsat = CP.Props('T','P',pressure,'Q',1,inletState.Fluid)
        elif 'pressure' in config['discharge']:
            pressure = config['discharge']['pressure']
            pratio = pressure / inletState.p
            Tsat = CP.Props('T','P',pressure,'Q',1,inletState.Fluid)
        else:
            raise ValueError('either pratio or pressure must be provided for discharge')
             
        disc_annotated_values = [
            AnnotatedValue('discPressure', pressure, *self.desc_map['discPressure']),
            AnnotatedValue('discPratio', pratio, *self.desc_map['discPratio']),
            AnnotatedValue('discTsat', Tsat, *self.desc_map['discTsat'])
            ]
        
        AGO_disc = self.construct_items(disc_annotated_values, sizer_for_discState)
        
        AGO_disc[0].GUI_location.Bind(wx.EVT_KILL_FOCUS,lambda event: self.OnChangeDischargeValue(event, 'pressure'))
        AGO_disc[1].GUI_location.Bind(wx.EVT_KILL_FOCUS,lambda event: self.OnChangeDischargeValue(event, 'pratio'))
        AGO_disc[2].GUI_location.Bind(wx.EVT_KILL_FOCUS,lambda event: self.OnChangeDischargeValue(event, 'Tsat'))
        
        self.main.register_GUI_objects([AGO_omega, AGO_inletState] + AGO_disc)
        
        sizer.Add(HeaderStaticText(self,'Rotational Speed'), 0, wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddSpacer(5)
        sizer.Add(sizer_for_omega, 0, wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddSpacer(5)
        sizer.Add(HeaderStaticText(self,'Inlet State'), 0, wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddSpacer(5)
        sizer.Add(self.SuctionStatePanel, 0, wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddSpacer(5)
        sizer.Add(HeaderStaticText(self, 'Discharge State'), 0, wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddSpacer(5)
        sizer.Add(sizer_for_discState, 0, wx.ALIGN_CENTER_HORIZONTAL)
        
        self.SetSizer(sizer)
        sizer.Layout()
        
    def OnChangeDischargeValue(self, event = None, changed_parameter = ''):
        """ 
        Set the internal pressure variable when the value is changed in the TextCtrl
        """
        suction_state = self.SuctionStatePanel.GetState() 
        psuction = suction_state.p
        Fluid = suction_state.Fluid
        
        if changed_parameter == 'pressure':
            pdisc = self.main.get_GUI_object_value('discPressure')
            pratio = pdisc / psuction
            Tsat = CP.Props('T', 'P', pdisc, 'Q', 1.0, Fluid)
            
        elif changed_parameter == 'pratio':
            pratio = self.main.get_GUI_object_value('discPratio')
            pdisc = psuction * pratio
            Tsat = CP.Props('T', 'P', pdisc, 'Q', 1.0, Fluid)
            
        elif changed_parameter == 'Tsat':
            Tsat = self.main.get_GUI_object_value('discTsat')
            pdisc = CP.Props('P', 'T', Tsat, 'Q', 1.0, Fluid)
            pratio = pdisc / psuction
            
        # Set all the values again
        self.main.set_GUI_object_value('discPressure',pdisc)
        self.main.set_GUI_object_value('discPratio',pratio)
        self.main.set_GUI_object_value('discTsat',Tsat)
        
    def get_config_chunk(self):
        
        inletState = self.SuctionStatePanel.GetState()
        
        configdict = {}
        configdict['omega'] = self.main.get_GUI_object_value('omega')
        configdict['discharge'] = dict(pressure = self.main.get_GUI_object_value('discPressure'))
        configdict['inletState'] = dict(Fluid = inletState.Fluid,
                                        T = inletState.T,
                                        rho = inletState.rho)
        
        return configdict
        
    def get_script_chunks(self):
        """
        Get a string for the script file that will be run
        """
        inletState = self.SuctionStatePanel.GetState()
        discPressure = self.main.get_GUI_object_value('discPressure')
        omega = self.main.get_GUI_object_value('omega')
    
        return textwrap.dedent(
            """
            inletState = State.State("{Ref:s}", {{'T': {Ti:s}, 'P' : {pi:s} }})
    
            T2s = sim.guess_outlet_temp(inletState,{po:s})
            outletState = State.State("{Ref:s}", {{'T':T2s,'P':{po:s} }})
            
            # The rotational speed (over-written if motor map provided)
            sim.omega = {omega:s}
            """.format(Ref = inletState.Fluid,
                       Ti = str(inletState.T),
                       pi = str(inletState.p),
                       po = str(discPressure),
                       omega = str(omega)
                       )
            )
    
    def post_set_params(self, simulation):
        Fluid = self.SuctionState.GetState().Fluid
        
        simulation.inletState = self.SuctionState.GetState()
            
        simulation.discharge_pressure = self._discharge_pressure
            
        #Set the state variables in the simulation
        simulation.suction_pressure = self.SuctionState.GetState().p
        simulation.suction_temp = self.SuctionState.GetState().T
        
        if self.SuctionState.GetState().p < CP.Props(Fluid,'pcrit'):
            #If subcritical, also calculate the superheat and sat_temp
            p = simulation.suction_pressure
            simulation.suction_sat_temp = CP.Props('T', 'P', p, 'Q', 1.0, Fluid)
            simulation.suction_superheat = simulation.suction_temp-simulation.suction_sat_temp
        else:
            #Otherwise remove the parameters
            del simulation.suction_sat_temp
            del simulation.suction_superheat
            
        #Set the state variables in the simulation
        simulation.discharge_pratio = simulation.discharge_pressure/simulation.suction_pressure
        
        if simulation.discharge_pressure < CP.Props(Fluid,'pcrit'):
            p = simulation.discharge_pressure
            simulation.discharge_sat_temp = CP.Props('T', 'P', p, 'Q', 1.0, Fluid)
        else:
            if hasattr(self,"discharge_sat_temp"):
                del simulation.discharge_sat_temp
        
    def post_prep_for_configfile(self):
        """
        Write a string representation of the state
        """
        State_ = self.SuctionState.GetState()
        StateString = 'inletState = State,'+State_.Fluid+','+str(State_.T)+','+str(State_.rho)
        DischargeString = 'discharge = Discharge,'+str(self.DischargeValue.GetValue())+','+self.cmbDischarge.GetStringSelection()
        return StateString+'\n'+DischargeString+'\n'
    
    def get_additional_parametric_terms(self):
        return [dict(attr = 'suction_pressure',
                     text = 'Suction pressure [kPa]',
                     parent = self),
                dict(attr = 'suction_sat_temp',
                     text = 'Suction saturated temperature (dew) [K]',
                     parent = self),
                dict(attr = 'suction_temp',
                     text = 'Suction temperature [K]',
                     parent = self),
                dict(attr = 'suction_superheat',
                     text = 'Superheat [K]',
                     parent = self),
                dict(attr = 'discharge_pressure',
                     text = 'Discharge pressure [kPa]',
                     parent = self),
                dict(attr = 'discharge_sat_temp',
                     text = 'Discharge saturated temperature (dew) [K]',
                     parent = self),
                dict(attr = 'discharge_pratio',
                     text = 'Discharge pressure ratio [-]',
                     parent = self)
                ]
    
    def apply_additional_parametric_terms(self, attrs, vals, panel_items):
        """
        Set parametric terms for the state panel based on parameters obtained
        from the parametric table
        """
        panel_attrs = [panel_item['attr'] for panel_item in panel_items]
        # First check about the suction state; if two suction related terms are 
        # provided, use them to fix the inlet state
        suct_params = [(par,val) for par,val in zip(attrs,vals) if par.startswith('suction')]
        num_suct_params = len(suct_params)
        
        #Get a copy of the state from the StatePanel
        inletState = self.SuctionState.GetState()
        
        if num_suct_params>0:
            #Unzip the parameters (List of tuples -> tuple of lists)
            suct_attrs, suct_vals = zip(*suct_params)
            
        if num_suct_params == 2:
            # Remove all the entries that correspond to the suction state - 
            # we need them and don't want to set them in the conventional way
            for a in suct_attrs:
                i = attrs.index(a)
                vals.pop(i)
                attrs.pop(i)
            
            #Temperature and pressure provided
            if 'suction_temp' in suct_attrs and 'suction_pressure' in suct_attrs:
                suction_temp = suct_vals[suct_attrs.index('suction_temp')]
                suction_pressure = suct_vals[suct_attrs.index('suction_pressure')]
                self.SuctionState.set_state(inletState.Fluid,
                                            T=suction_temp, 
                                            P=suction_pressure)
                
            #Dew temperature and superheat provided
            elif 'suction_sat_temp' in suct_attrs and 'suction_superheat' in suct_attrs:
                suction_sat_temp = suct_vals[suct_attrs.index('suction_sat_temp')]
                suction_superheat = suct_vals[suct_attrs.index('suction_superheat')]
                suction_temp = suction_sat_temp + suction_superheat
                suction_pressure = CP.Props('P','T',suction_sat_temp,'Q',1.0,inletState.Fluid)
                self.SuctionState.set_state(inletState.Fluid,
                                            T=suction_temp, 
                                            P=suction_pressure)
            else:
                raise ValueError('Invalid combination of suction states: '+str(suct_attrs))
            
        elif num_suct_params == 1:
            raise NotImplementedError('only one param provided')
        elif num_suct_params >2:
            raise ValueError ('Only two inlet state parameters can be provided in parametric table')
        
        # Then check about the discharge state; only one variable is allowed
        disc_params = [(par,val) for par,val in zip(attrs,vals) if par.startswith('discharge')]
        num_disc_params = len(disc_params)
        
        if num_disc_params>0:
            #Unzip the parameters (List of tuples -> tuple of lists)
            disc_attrs, disc_vals = zip(*disc_params)
            
        if num_disc_params == 1:
            # Remove all the entries that correspond to the discharge state - 
            # we need them and don't want to set them in the conventional way
            for a in disc_attrs:
                i = attrs.index(a)
                vals.pop(i)
                attrs.pop(i)
                
            if 'discharge_pressure' in disc_attrs:
                discharge_pressure = disc_vals[disc_attrs.index('discharge_pressure')]
                self._discharge_pressure = discharge_pressure
                
            elif 'discharge_pratio' in disc_attrs:
                discharge_pratio = disc_vals[disc_attrs.index('discharge_pratio')]
                p_suction = self.SuctionState.GetState().p
                self._discharge_pressure = discharge_pratio * p_suction
        
            elif 'discharge_sat_temp' in disc_attrs:
                Tsat = disc_vals[disc_attrs.index('discharge_sat_temp')]
                Fluid = inletState.Fluid
                self._discharge_pressure = CP.Props('P','T',Tsat,'Q',1.0,Fluid)
            
            #Fire the event manually to update the textbox
            self.OnChangeDischargeVariable()
            
        elif num_disc_params > 1:
            raise ValueError ('Only one discharge pressure parameter can be provided in parametric table')
            
        return attrs, vals
    
class MotorCoeffsTable(wx.ListCtrl, TextEditMixin):
    
    def __init__(self, parent, values = None):
        """
        Parameters
        ----------
        parent : wx.window
            The parent of this checklist
        values : A 3-element list of lists for all the coeff
        """
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT)
        TextEditMixin.__init__(self)
        
        #Build the headers
        self.InsertColumn(0,'Motor Torque [N-m]')
        self.InsertColumn(1,'Efficiency [-]')
        self.InsertColumn(2,'Slip speed [rad/s]')
        
        #: The values stored as a list of lists in floating form
        self.values = values
        
        #Reset the values
        self.refresh_table()
        
        #Set the column widths    
        for i in range(3):
            self.SetColumnWidth(i,wx.LIST_AUTOSIZE_USEHEADER)
        
        # Turn on callback to write values back into internal data structure when
        # a cell is edited
        self.Bind(wx.EVT_LIST_END_LABEL_EDIT, self.OnCellEdited)
        
        #Required width for the table
        min_width = sum([self.GetColumnWidth(i) for i in range(self.GetColumnCount())])
        
        #No required height (+30 for buffer to account for vertical scroll bar)
        self.SetMinSize((min_width + 30,-1))

    def OnCellEdited(self, event):
        """
        Once the cell is edited, write its value back into the data matrix
        """
        row_index = event.m_itemIndex
        col_index = event.Column
        val = float(event.Text)
        self.data[row_index][col_index-1] = val
    
    def GetStringCell(self,Irow,Icol):
        """ Returns a string representation of the cell """
        return self.data[Irow][Icol]
    
    def GetFloatCell(self,Irow,Icol):
        """ Returns a float representation of the cell """
        return float(self.data[Irow][Icol])
    
    def AddRow(self):
        
        row = [0]*self.GetColumnCount()
        
        i = len(self.data)-1
        self.InsertStringItem(i,'')
        for j,val in enumerate(row):
            self.SetStringItem(i,j+1,str(val))
        self.CheckItem(i)
        
        self.data.append(row)
        
    def RemoveRow(self, i = 0):
        self.data.pop(i)
        self.DeleteItem(i)
        
    def RemoveLastRow(self):
        i = len(self.data)-1
        self.data.pop(i)
        self.DeleteItem(i)
    
    def update_from_configfile(self, values):
        """
        
        Parameters
        ----------
        values : list of lists, with entries as floating point values
            The first entry is a list (or other iterable) of torque values
            
            The second entry is a list (or other iterable) of efficiency values
            
            The third entry is a list (or other iterable) of slip speed values
        """
        self.values = values
        self.refresh_table()
        
    def string_for_configfile(self):
        """
        Build and return a string for writing to the config file
        """
            
        tau_list = self.values[0]
        tau_string = 'tau_motor_coeffs = coeffs, '+'; '.join([str(tau) for tau in tau_list])
        
        eta_list = self.values[1]
        eta_string = 'eta_motor_coeffs = coeffs, '+'; '.join([str(eta) for eta in eta_list])
        
        omega_list = self.values[2]
        omega_string = 'omega_motor_coeffs = coeffs, '+'; '.join([str(omega) for omega in omega_list])
            
        return tau_string + '\n' + eta_string + '\n' + omega_string + '\n'
        
        
    def refresh_table(self):
        """
        Take the values from self.values and write them to the table
        """
        #Remove all the values in the table
        for i in reversed(range(self.GetItemCount())):
            self.DeleteItem(i)
            
        if self.values is None:
            #Add a few rows
            for i in range(10):
                self.InsertStringItem(i,str(i))
        else:
            #They all need to be the same length
            assert len(self.values[0]) == len(self.values[1]) == len(self.values[2])
            for i in range(len(self.values[0])):
                self.InsertStringItem(i,str(self.values[0][i]))
                self.SetStringItem(i,1,str(self.values[1][i]))
                self.SetStringItem(i,2,str(self.values[2][i]))
                
    def get_coeffs(self):
        """
        Get the list of lists of values that are used in the table
        """
        return self.values
        
class MotorChoices(wx.Choicebook):
    def __init__(self, parent):
        wx.Choicebook.__init__(self, parent, -1)
        
        self.pageconsteta=wx.Panel(self)
        self.AddPage(self.pageconsteta,'Constant efficiency')
        self.eta_motor_label, self.eta_motor = LabeledItem(self.pageconsteta, 
                                                           label="Motor Efficiency [-]",
                                                           value='0.9')
        sizer=wx.FlexGridSizer(cols = 2, hgap = 3, vgap = 3)
        sizer.AddMany([self.eta_motor_label, self.eta_motor])
        self.pageconsteta.SetSizer(sizer)
        
        self.pagemotormap=wx.Panel(self)
        self.AddPage(self.pagemotormap,'Motor map')
        self.MCT = MotorCoeffsTable(self.pagemotormap,values = [[1,2,3],[0.9,0.9,0.9],[307,307,307]])
        sizer=wx.FlexGridSizer(cols = 2, hgap = 3, vgap = 3)
        sizer.Add(self.MCT, 1, wx.EXPAND)
        self.pagemotormap.SetSizer(sizer)
        sizer.Layout()
        
if __name__=='__main__':    
    
    execfile('PDSimGUI.py')