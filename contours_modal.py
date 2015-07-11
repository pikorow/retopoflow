'''
Copyright (C) 2015 Taylor University, CG Cookie

Created by Dr. Jon Denning and Spring 2015 COS 424 class

Some code copied from CG Cookie Retopoflow project
https://github.com/CGCookie/retopoflow

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import bpy
import bgl
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_vector_3d
from bpy_extras.view3d_utils import region_2d_to_location_3d, region_2d_to_origin_3d
from mathutils import Vector, Matrix
import math
import os


from .modaloperator import ModalOperator
from . import key_maps
from .lib import common_utilities
from .lib.common_utilities import bversion, get_object_length_scale, dprint, profiler, frange, selection_mouse, showErrorMessage
from .contour_classes import Contours
from .lib.common_utilities import showErrorMessage

class  CGC_Contours(ModalOperator):
    '''Draw Strokes Perpindicular to Cylindrical Forms to Retopologize Them'''
    bl_category = "Retopology"
    bl_idname = "cgcookie.contours"      # unique identifier for buttons and menu items to reference
    bl_label = "Contours"       # display name in the interface
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    #bl_options = {'REGISTER', 'UNDO'}       # enable undo for the operator.
    
    def __init__(self):
        FSM = {}
        FSM['main loop']    = self.modal_loop
        FSM['main guide']   = self.modal_guide
        FSM['cutting']      = self.modal_cut
        FSM['sketch']       = self.modal_sketching
        FSM['widget']       = self.modal_widget
        '''
        main, nav, and wait states are automatically added in initialize function, called below.
        '''
        self.initialize(FSM)
    
    def start_poll(self,context):
        if context.space_data.viewport_shade in {'WIREFRAME','BOUNDBOX'}:
            showErrorMessage('Viewport shading must be at least SOLID')
            return False
        elif context.mode == 'EDIT_MESH' and len(context.selected_objects) != 2:
            showErrorMessage('Must select exactly two objects')
            return False
        elif context.mode == 'OBJECT' and len(context.selected_objects) != 1:
            showErrorMessage('Must select only one object')
            return False
        return True
    
    def start(self, context):
        ''' Called when tool has been invoked '''
        print('did we get started')
        self.settings = common_utilities.get_settings()
        self.keymap = key_maps.rtflow_default_keymap_generate()
        self.get_help_text(context)
        self.contours = Contours(context, self.settings)
        return ''
    
    def modal_wait(self, context, eventd):
        #simple messaging
        if self.footer_last != self.footer:
            context.area.header_text_set('Contours: %s' % self.footer)
            self.footer_last = self.footer
        
        #contours mode toggle
        if eventd['press'] in self.keymap['mode']:
            if self.contours.mode == 'loop':
                self.contours.mode_set_guide()
                self.contours.mode = 'guide'
            else:
                self.contours.mode_set_loop()
                self.contours.mode = 'loop'
            return ''
        
        elif eventd['press'] in self.keymap['help']:
            if  self.help_box.is_collapsed:
                self.help_box.uncollapse()
            else:
                self.help_box.collapse()
            self.help_box.snap_to_corner(eventd['context'],corner = [1,1])
        
        elif eventd['press'] in self.keymap['undo']:
            self.contours.undo_action()
            return ''
            
        if self.contours.mode == 'loop':
            return self.modal_loop(context,eventd)
        else:
            return self.modal_guide(context,eventd)
         
    
    def modal_loop(self, context, eventd): 
        if self.footer != 'Loop Mode': self.footer = 'Loop Mode'
        
        if eventd['type'] == 'MOUSEMOVE':  #mouse movement/hovering widget
            x,y = eventd['mouse']
            self.help_box.hover(x,y)
            self.contours.hover_loop_mode(eventd['context'], self.settings, x,y)
            return ''
        
        if eventd['press'] in selection_mouse(): #self.keymap['select']: # selection
            ret = self.contours.loop_select(eventd['context'], eventd)
            if ret:
                return ''    
        
        if eventd['press'] in self.keymap['action']:   # cutting and widget hard coded to LMB
            if self.help_box.is_hovered:
                if  self.help_box.is_collapsed:
                    self.help_box.uncollapse()
                else:
                    self.help_box.collapse()
                self.help_box.snap_to_corner(eventd['context'],corner = [1,1])
            
                return ''
            
            if self.contours.cut_line_widget:
                self.contours.prepare_widget(eventd)
                return 'widget'
            
            else:
                self.footer = 'Cutting'
                x,y = eventd['mouse']
                self.contours.sel_loop = self.contours.click_new_cut(eventd['context'], self.settings, x,y)    
                return 'cutting'
        
        if eventd['press'] in self.keymap['new']:
            self.contours.force_new = self.contours.force_new != True
            return ''
        
        ###################################
        # selected contour loop commands
        
        if self.contours.sel_loop:
            if eventd['press'] in self.keymap['delete']:
                self.contours.loops_delete(context, [self.contours.sel_loop])
                return ''
        
            if eventd['press'] in self.keymap['align']:
                self.contours.loop_align(context, eventd)
                return ''
            elif eventd['press'] in self.keymap['up shift']:
                self.contours.loop_shift(context, eventd, up = True)
                return ''        
            elif eventd['press'] in self.keymap['dn shift']:
                self.contours.loop_shift(context, eventd, up = False)
                return ''
            elif eventd['press'] in self.keymap['up count']:
                n = len(self.contours.sel_loop.verts_simple)
                self.contours.loop_nverts_change(context, eventd, n+1)    
                return ''
            elif eventd['press'] in self.keymap['dn count']:
                n = len(self.sel_loop.verts_simple)
                self.contours.loop_nverts_change(context, eventd, n-1)
                return ''
        
            elif eventd['press'] in self.keymap['snap cursor']:
                context.scene.cursor_location = self.contours.sel_loop.plane_com
                return ''
            elif eventd['press'] in self.keymap['view cursor']:
                bpy.ops.view3d.view_center_cursor()
                return ''
        
            elif eventd['press'] in self.keymap['rotate']:
                self.contours.prepare_rotate(context,eventd)
                #header text handled during rotation
                return 'widget'
            
            if eventd['press'] in self.keymap['translate']:
                self.contours.prepare_translate(context, eventd)
                #header text handled during translation
                return 'widget'
        return ''

    def modal_guide(self, context, eventd):
        if self.footer != 'Guide Mode': self.footer = 'Guide Mode'
        
        if eventd['press'] in self.keymap['new']:
            self.contours.force_new = self.contours.force_new != True
            return '' 
        
        if eventd['type'] == 'MOUSEMOVE':  #mouse movement/hovering widget
            x,y = eventd['mouse']
            self.help_box.hover(x,y)
            self.contours.hover_guide_mode(eventd['context'], self.settings, x, y)
            return ''
        
        if eventd['press'] in selection_mouse(): #self.keymap['select']: # selection
            self.contours.guide_mode_select()   
            return ''
        
        if eventd['press'] in self.keymap['action']: #LMB hard code for sketching
            
            if self.help_box.is_hovered:
                if  self.help_box.is_collapsed:
                    self.help_box.uncollapse()
                else:
                    self.help_box.collapse()
                self.help_box.snap_to_corner(eventd['context'],corner = [1,1])
                return ''
            
            self.footer = 'sketching'
            x,y = eventd['mouse']
            self.contours.sketch = [(x,y)] 
            return 'sketch'
        
        if self.contours.sel_path:
            if eventd['press'] in self.keymap['delete']:
                self.contours.create_undo_snapshot('DELETE')
                self.contours.cut_paths.remove(self.sel_path)
                self.contours.sel_path = None
                return ''
            
            if eventd['press'] in self.keymap['up shift']:
                self.contours.segment_shift(eventd['context'], up = True)
                return ''
            
            if eventd['press'] in self.keymap['dn shift']:
                self.contours.segment_shift(eventd['context'], up = False)
                return 
            
            if eventd['press'] in self.keymap['up count']:
                n = self.contours.sel_path.segments + 1
                if self.contours.sel_path.seg_lock: #TODO showError(yada yada)
                    showErrorMessage('PATH SEGMENTS: Path is locked, cannot adjust segments')
                else:
                    self.contours.segment_n_loops(eventd['context'], self.contours.sel_path, n)    
                #self.temporary_message_start(eventd['context'], 'PATH SEGMENTS: %i' % n)
                return ''
            
            if eventd['press'] in self.keymap['dn count']:
                n = self.sel_path.segments - 1
                if self.sel_path.seg_lock:
                    return ''
                    showErrorMessage('PATH SEGMENTS: Path is locked, cannot adjust segments')
                    #self.temporary_message_start(eventd['context'], 'PATH SEGMENTS: Path is locked, cannot adjust segments')
                elif n < 3:
                    #self.temporary_message_start(eventd['context'], 'PATH SEGMENTS: You want more segments than that!')
                    return ''
                else:
                    self.contours.segment_n_loops(eventd['context'], self.contours.sel_path, n)    
                    #self.temporary_message_start(eventd['context'], 'PATH SEGMENTS: %i' % n)
                return ''
            
            if eventd['press'] in self.keymap['smooth']:
                
                self.contours.segment_smooth(eventd['context'], self.settings)
                #messaging handled in operator
                return ''
            
            if eventd['press'] in self.keymap['snap cursor']:
                self.contours.cursor_to_segment(eventd['context'])
                #self.temporary_message_start(eventd['context'], 'Cursor to Segment')
                return ''
             
             
            if eventd['press'] in self.keymap['view cursor']:
                bpy.ops.view3d.view_center_cursor()
                return ''    
        return ''
    
    def modal_cut(self, context, eventd):
        if self.footer != 'Cutting': self.footer = 'Cutting'
        
        if eventd['type'] == 'MOUSEMOVE':
            x,y = eventd['mouse']
            self.contours.sel_loop.tail.x, self.contours.sel_loop.tail.y  = x, y    
            return ''
        
        if eventd['release'] in self.keymap['action']: #LMB hard code for cut
            print('new cut made')
            x,y = eventd['mouse']
            self.contours.release_place_cut(eventd['context'], self.settings, x, y)
            return 'main'
        
        return ''
        
    def modal_sketching(self, context, eventd):
        if self.footer != 'Sketching': self.footer = 'Sketching'
        
        if eventd['type'] == 'MOUSEMOVE':
            x,y = eventd['mouse']
            self.sketch_curpos = (x,y)
            
            if not len(self.contours.sketch):
                #somehow we got into sketching w/o sketching
                return 'main'
            
            (lx, ly) = self.contours.sketch[-1]
            #on the fly, backwards facing, smoothing
            ss0,ss1 = self.contours.stroke_smoothing,1-self.contours.stroke_smoothing
            self.contours.sketch += [(lx*ss0+x*ss1, ly*ss0+y*ss1)] #vs append?         
            return ''
        
        elif eventd['release'] in self.keymap['action']:
            self.contours.sketch_confirm(eventd['context']) 
            return 'main'
        
        
        return ''
    
    def modal_widget(self,context,eventd):
        if self.footer != 'Widget': self.footer = 'Widget'
        
        if eventd['type'] == 'MOUSEMOVE':
            self.contours.widget_transform(context, self.settings, eventd)
            return ''
        
        elif eventd['release'] in self.keymap['action'] | self.keymap['modal confirm']:
            self.contours.cut_line_widget = None
            self.contours.sel_path.update_backbone(context, self.contours.original_form, self.contours.bme, self.contours.sel_loop, insert = False)
            return 'main'
        
        elif eventd['press'] in self.keymap['modal cancel']:
            self.contours.widget_cancel(context)
            return 'main'
        return ''
    
    def update(self,context):
        pass
    
    def end(self, context):
        ''' Called when tool is ending modal '''
        pass
    
    def end_commit(self, context):
        ''' Called when tool is committing '''
        self.contours.finish_mesh(context)
        pass
    
    def end_cancel(self, context):
        ''' Called when tool is canceled '''
        pass
    
    def draw_postview(self, context):
        ''' Place post view drawing code in here '''
        pass
    
    def draw_postpixel(self, context):
        ''' Place post pixel drawing code in here '''
        
        self.contours.draw_post_pixel(context)
        self.help_box.draw()
        pass
    
    def get_help_text(self,context):
        my_dir = os.path.split(os.path.abspath(__file__))[0]
        filename = os.path.join(my_dir, "help/help_contours.txt")
        if os.path.isfile(filename):
            help_txt = open(filename, mode='r').read()
        else:
            help_txt = "No Help File found, please reinstall!"
    
        self.help_box.raw_text = help_txt
        if not self.settings.help_def:
            self.help_box.collapse()
        self.help_box.snap_to_corner(context, corner = [1,1])
