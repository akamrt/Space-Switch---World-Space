"""
Space Switch Dashboard for Maya 2023
=====================================
An animator-focused dashboard for space switching with anti-gimbal lock features.

USAGE:
    Copy and paste this entire script into Maya's Script Editor and run.
    The dashboard will appear as a dockable window.

THREE-STAGE WORKFLOW:
    1. CREATE  - Build locator hierarchy and position from current frame
    2. BAKE    - Bake animation to locators with cleanup
    3. REBUILD - Apply constraints back to original objects

Auto-reloads when re-run for fast iteration during development.
"""

# ============================================================================
# IMPORTS
# ============================================================================
import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om
import math
from functools import partial

# Qt — try the Maya bundled shim first, fall back to bare PySide2 / PyQt5
try:
    from Qt import QtWidgets, QtGui, QtCore
except ImportError:
    try:
        from PySide2 import QtWidgets, QtGui, QtCore
    except ImportError:
        from PyQt5 import QtWidgets, QtGui, QtCore

# Maya main-window handle (used to parent the dashboard as a proper child window)
try:
    from maya import OpenMayaUI as omui
    try:
        from shiboken2 import wrapInstance
    except ImportError:
        from shiboken6 import wrapInstance
    def _maya_main_window():
        ptr = omui.MQtUtil.mainWindow()
        return wrapInstance(int(ptr), QtWidgets.QWidget)
except Exception:
    def _maya_main_window():
        return None

# ============================================================================
# CONSTANTS
# ============================================================================
WINDOW_NAME = "spaceSwitchDashboard"
WINDOW_TITLE = "Space Switch Dashboard"
LOCATOR_SUFFIX = "_SS_loc"
OFFSET_SUFFIX = "_offset"
GIMBAL_SUFFIX = "_gimbal"

# Color palette for locators (Maya override colors)
LOCATOR_COLORS = {
    "red": 13,
    "yellow": 17,
    "green": 14,
    "blue": 6,
    "purple": 9,
    "white": 16,
    "cyan": 18,
    "orange": 21,
}

ROTATION_ORDERS = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]

# ============================================================================
# CYBERPUNK STYLESHEET
# ============================================================================
CYBERPUNK_SS = """
QWidget {
    background-color: #1A1A2E;
    color: #B0BEC5;
    font-family: "Courier New", Courier, monospace;
    font-size: 11px;
}
QGroupBox {
    border: 1px solid #4DD0E1;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: -1px;
    color: #4DD0E1;
    font-weight: bold;
    letter-spacing: 1px;
    background-color: #1A1A2E;
    padding: 0 4px;
}
QPushButton {
    background-color: #0F3460;
    color: #B0BEC5;
    border: 1px solid #4DD0E1;
    border-radius: 3px;
    padding: 5px 10px;
}
QPushButton:hover {
    background-color: #4DD0E1;
    color: #1A1A2E;
    font-weight: bold;
}
QPushButton:pressed {
    background-color: #00BCD4;
    color: #1A1A2E;
}
QLineEdit {
    background-color: #0F1923;
    border: 1px solid #2E4A5A;
    border-radius: 3px;
    color: #4DD0E1;
    padding: 3px 6px;
    selection-background-color: #4DD0E1;
    selection-color: #1A1A2E;
}
QLineEdit:focus {
    border-color: #4DD0E1;
}
QCheckBox {
    color: #B0BEC5;
    spacing: 5px;
}
QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #4DD0E1;
    border-radius: 2px;
    background-color: #0F1923;
}
QCheckBox::indicator:checked {
    background-color: #4DD0E1;
}
QRadioButton {
    color: #B0BEC5;
    spacing: 5px;
}
QRadioButton::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #4DD0E1;
    border-radius: 7px;
    background-color: #0F1923;
}
QRadioButton::indicator:checked {
    background-color: #4DD0E1;
}
QComboBox {
    background-color: #0F3460;
    border: 1px solid #4DD0E1;
    border-radius: 3px;
    color: #E0E0E0;
    padding: 3px 8px;
    min-height: 22px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #4DD0E1;
}
QComboBox QAbstractItemView {
    background-color: #16213E;
    border: 1px solid #4DD0E1;
    color: #E0E0E0;
    selection-background-color: #4DD0E1;
    selection-color: #1A1A2E;
}
QSlider::groove:horizontal {
    border: 1px solid #4DD0E1;
    height: 4px;
    background: #0F1923;
    border-radius: 2px;
    margin: 0;
}
QSlider::handle:horizontal {
    background: #4DD0E1;
    border: 1px solid #4DD0E1;
    width: 12px;
    height: 12px;
    border-radius: 6px;
    margin: -5px 0;
}
QSlider::sub-page:horizontal {
    background: #4DD0E1;
    border-radius: 2px;
}
QSpinBox, QDoubleSpinBox {
    background-color: #0F1923;
    border: 1px solid #2E4A5A;
    border-radius: 3px;
    color: #4DD0E1;
    padding: 2px 4px;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #0F3460;
    border: 1px solid #4DD0E1;
    width: 14px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #4DD0E1;
}
QLabel {
    color: #B0BEC5;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollBar:vertical {
    background-color: #0F1923;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #4DD0E1;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
"""


# ============================================================================
# SPACE SWITCHER CORE LOGIC
# ============================================================================
class SpaceSwitcher:
    """Core logic for space switching operations."""
    
    def __init__(self):
        self.created_locators = []
        self.source_objects = []
        self.temp_constraints = []

    def get_best_rotation_order(self, source_obj, start_time, end_time):
        """
        Calculate the best rotation order to minimize gimbal lock.
        Analyzes the source object's world rotation over the time range.
        Middle axis approaching +/- 90 degrees is bad.
        """
        if not cmds.objExists(source_obj):
            return 0 # Default xyz

        # Valid orders in Maya which map to MTransformationMatrix constants
        # 0: kXYZ, 1: kYZX, 2: kZXY, 3: kXZY, 4: kYXZ, 5: kZYX
        # Middle axes corresponding to these orders:
        # 0 (xyz) -> Y (1)
        # 1 (yzx) -> Z (2)
        # 2 (zxy) -> X (0)
        # 3 (xzy) -> Z (2)
        # 4 (yxz) -> X (0)
        # 5 (zyx) -> Y (1)
        middle_axis_map = {0: 1, 1: 2, 2: 0, 3: 2, 4: 0, 5: 1}
        
        # Map Maya's attribute integers (0-5) to OpenMaya MTransformationMatrix constants
        # Note: In API 2.0, kXYZ is 1, not 0. 0 is kInvalid.
        om_order_map = {
            0: om.MTransformationMatrix.kXYZ,
            1: om.MTransformationMatrix.kYZX,
            2: om.MTransformationMatrix.kZXY,
            3: om.MTransformationMatrix.kXZY,
            4: om.MTransformationMatrix.kYXZ,
            5: om.MTransformationMatrix.kZYX
        }
        
        # Track the max deviation (score) for each order.
        # Score = Max value of abs(middle_axis_angle). Lower is better (further from 90 deg/1.57 rad).
        scores = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}

        # Sample frames — stride large ranges so long shots stay fast.
        all_frames = list(range(int(start_time), int(end_time) + 1))
        MAX_SAMPLES = 200
        if len(all_frames) > MAX_SAMPLES:
            stride = max(1, len(all_frames) // MAX_SAMPLES)
            frames = all_frames[::stride]
            # Always include the last frame so we don't miss end-of-shot poses.
            if frames[-1] != all_frames[-1]:
                frames.append(all_frames[-1])
        else:
            frames = all_frames

        print(f"Analyzing {len(frames)} frames (of {len(all_frames)}) for best rotation "
              f"order on '{source_obj}'...")

        world_attr = f"{source_obj}.worldMatrix[0]"
        for t in frames:
            try:
                # Get World Matrix at frame t — ONCE per frame, reuse across all six orders.
                mat = om.MMatrix(cmds.getAttr(world_attr, time=t))
                base_euler = om.MTransformationMatrix(mat).rotation()  # default XYZ

                for order_idx, middle_axis_idx in middle_axis_map.items():
                    # Copy + reorder; cheap compared to rebuilding the full transform.
                    e = om.MEulerRotation(base_euler)
                    e.reorderIt(om_order_map[order_idx])

                    # Middle axis value in radians — closer to 0 is better, PI/2 is gimbal.
                    mid_val = abs(e[middle_axis_idx])
                    if mid_val > scores[order_idx]:
                        scores[order_idx] = mid_val

            except Exception as e:
                print(f"Error analyzing frame {t}: {e}")
                continue

        # Find order with lowest max deviation
        best_order = min(scores, key=scores.get)
        
        # Debug Output
        print("Rotation Order Scores (Lower max deviation is better):")
        for order_idx, score in scores.items():
            mark = " [BEST]" if order_idx == best_order else ""
            print(f"  {ROTATION_ORDERS[order_idx].upper()}: Max Middle Axis = {math.degrees(score):.2f} deg{mark}")
            
        print(f"Selected Best Order: {ROTATION_ORDERS[best_order].upper()}")
        return best_order

    
    def create_locator_hierarchy(self, source_obj, target_obj=None, mode="world", 
                                  num_offsets=2, locator_size=1, 
                                  color_index=17, rotation_order=0, hide_offset=True):
        """
        Create locator hierarchy with Master Space node.
        Hierarchy: Master(Space) -> Top_Offset(Baked) -> [Gimbal] -> Locator(Control)
        """
        if not source_obj:
            return None, None, None
            
        base_name = source_obj.replace(":", "_").replace("|", "_")
        
        # 1. Create MASTER Group (The Space Node)
        master_name = f"{base_name}_Master_Space"
        master_grp = cmds.group(empty=True, name=master_name)
        cmds.setAttr(f"{master_grp}.rotateOrder", rotation_order)
        
        # Setup Master Space transform/constraints
        if mode == "world":
            # World space: Master stays at origin (Identity)
            pass 
        elif mode == "local":
             # Local space: Match Source Initial
             cmds.matchTransform(master_grp, source_obj, position=True, rotation=True)
             
        elif mode in ["object", "camera", "aim"]:
            # These modes REQUIRE a target
            if not target_obj or not cmds.objExists(target_obj):
                cmds.warning(f"Create Hierarchy: Target '{target_obj}' invalid for mode '{mode}'. Master staying at origin.")
            else:
                # Match Target Pivot first
                cmds.matchTransform(master_grp, target_obj, position=True, rotation=True)
                
                # Apply Space Constraints
                if mode == "object":
                    # STRICT SNAP to target (False) ensuring we adopt its space exactly
                    cmds.parentConstraint(target_obj, master_grp, maintainOffset=False)
                elif mode == "camera":
                    cmds.parentConstraint(target_obj, master_grp, maintainOffset=False)
                elif mode == "aim":
                    # Aim Space: Master positioned at Target, Aiming at Source.
                    # Static setup: Constraints are applied and then deleted immediately so Master is static.
                    cmds.matchTransform(master_grp, target_obj, position=True)
                    
                    # Aim at Source (X-axis)
                    ac = cmds.aimConstraint(source_obj, master_grp, maintainOffset=False, 
                                       aimVector=(1,0,0), upVector=(0,1,0), worldUpType="scene")
                    cmds.delete(ac)

        # 2. Create Locator Chain (Child of Master)
        # Create the main control locator (bottom of chain)
        locator_name = base_name + LOCATOR_SUFFIX
        locator = cmds.spaceLocator(name=locator_name)[0]
        
        # Set locator visuals
        cmds.setAttr(f"{locator}.localScaleX", locator_size)
        cmds.setAttr(f"{locator}.localScaleY", locator_size)
        cmds.setAttr(f"{locator}.localScaleZ", locator_size)
        locator_shape = cmds.listRelatives(locator, shapes=True)[0]
        cmds.setAttr(f"{locator_shape}.overrideEnabled", 1)
        cmds.setAttr(f"{locator_shape}.overrideColor", color_index)
        cmds.setAttr(f"{locator}.rotateOrder", rotation_order)
        # Expose rotateOrder in Channel Box
        cmds.setAttr(f"{locator}.rotateOrder", k=True)
        # Hide the bottom child locator — it's a technical driver, not an animator handle
        if hide_offset:
            cmds.setAttr(f"{locator_shape}.visibility", 0)
        
        # Build offset hierarchy strictly above locator
        current_child = locator
        top_offset = locator
        
        for i in range(num_offsets):
            offset_name = f"{base_name}{OFFSET_SUFFIX}_{i+1}"
            if i == 0:
                offset_name = f"{base_name}{GIMBAL_SUFFIX}"
            
            is_top_offset = (i == num_offsets - 1)
            
            if is_top_offset:
                # The top offset holds the baked animation
                offset_grp = cmds.spaceLocator(name=offset_name)[0]
                # Expose rotateOrder in Channel Box
                cmds.setAttr(f"{offset_grp}.rotateOrder", k=True)
                
                # Visuals for baked locator
                top_size = locator_size * 1.2
                cmds.setAttr(f"{offset_grp}.localScaleX", top_size)
                cmds.setAttr(f"{offset_grp}.localScaleY", top_size)
                cmds.setAttr(f"{offset_grp}.localScaleZ", top_size)
                shape = cmds.listRelatives(offset_grp, shapes=True)[0]
                cmds.setAttr(f"{shape}.overrideEnabled", 1)
                cmds.setAttr(f"{shape}.overrideColor", color_index)
                # Top offset is the animator's baked control — keep it visible
            else:
                offset_grp = cmds.group(empty=True, name=offset_name)
            
            cmds.setAttr(f"{offset_grp}.rotateOrder", rotation_order)
            
            cmds.parent(current_child, offset_grp)
            current_child = offset_grp
            top_offset = offset_grp
            
        # 3. Parent Chain to Master
        # Match chain to source object current position BEFORE parenting
        cmds.matchTransform(top_offset, source_obj, position=True, rotation=True)
        cmds.parent(top_offset, master_grp)
        
        # Store reference
        self.created_locators.append({
            "source": source_obj,
            "locator": locator,
            "top_group": top_offset, # The one defined as baked target
            "master": master_grp,
            "hierarchy": self._get_hierarchy(master_grp)
        })
        
        return top_offset, locator, master_grp
    
    def _get_hierarchy(self, top_node):
        """Get all nodes in the hierarchy."""
        hierarchy = [top_node]
        children = cmds.listRelatives(top_node, allDescendents=True, type="transform") or []
        hierarchy.extend(children)
        return hierarchy
    
    def create_temp_constraints(self, source_obj, target_node, translate=True, rotate=True):
        """
        Create temporary constraints from source to target for baking.
        
        Args:
            source_obj: The source object to follow
            target_node: The node to constrain (should be top_group for proper hierarchy)
            translate: Apply point constraint
            rotate: Apply orient constraint
        """
        constraints = []
        
        if translate:
            pc = cmds.pointConstraint(source_obj, target_node, maintainOffset=False)[0]
            constraints.append(pc)
        
        if rotate:
            oc = cmds.orientConstraint(source_obj, target_node, maintainOffset=False)[0]
            constraints.append(oc)
        
        self.temp_constraints.extend(constraints)
        return constraints
    
    def create_aim_constraint(self, source_obj, target_node, aim_target_obj):
        """
        Create aim constraint for object space aiming.
        
        Args:
            source_obj: The source object (for reference)
            target_node: The node to constrain (should be top_group)
            aim_target_obj: The object to aim at
        """
        ac = cmds.aimConstraint(
            aim_target_obj, target_node,
            maintainOffset=False,
            aimVector=(0, 0, 1),
            upVector=(0, 1, 0),
            worldUpType="vector",
            worldUpVector=(0, 1, 0)
        )[0]
        self.temp_constraints.append(ac)
        return ac
    
    def bake_animation(self, locators, sample_by=1, euler_filter=True, cleanup_constraints=True, destination_layer=None):
        """
        Bake animation to locators.
        
        Args:
            locators: List of locator names to bake
            sample_by: Sample rate for baking
            euler_filter: Apply Euler filter after baking
            cleanup_constraints: Whether to delete temporary constraints
            destination_layer: Name of animation layer to bake onto (optional)
        """
        if not locators:
            return
        
        start_time = cmds.playbackOptions(query=True, minTime=True)
        end_time = cmds.playbackOptions(query=True, maxTime=True)
        
        cmds.refresh(suspend=True)
        try:
            bake_args = {
                "simulation": True,
                "time": (start_time, end_time),
                "sampleBy": sample_by,
                "disableImplicitControl": True,
                "preserveOutsideKeys": True,
                "sparseAnimCurveBake": True,
                "removeBakedAttributeFromLayer": False,
                "removeBakedAnimFromLayer": False,
                "bakeOnOverrideLayer": False,
                "minimizeRotation": True,
                "controlPoints": False
            }

            if destination_layer:
                bake_args["destinationLayer"] = destination_layer

            cmds.bakeResults(locators, **bake_args)
            
            # Delete temporary constraints
            if cleanup_constraints:
                for constraint in self.temp_constraints:
                    if cmds.objExists(constraint):
                        cmds.delete(constraint)
                self.temp_constraints = []
            
            # Ensure rotateOrder has no keys (it should be static)
            for loc in locators:
                if cmds.objExists(loc):
                    # Store the correct rotation order value
                    ro_val = cmds.getAttr(f"{loc}.rotateOrder")
                    # Remove any keys that might have been baked
                    cmds.cutKey(loc, attribute="rotateOrder", clear=True)
                    # Explicitly restore the value to ensure it doesn't revert to default
                    cmds.setAttr(f"{loc}.rotateOrder", ro_val)

            # Apply Euler filter
            if euler_filter:
                cmds.select(locators)
                cmds.filterCurve()
            
        finally:
            cmds.refresh(suspend=False)
    
    def cleanup_keys(self, locators, threshold=0.001):
        """
        Clean up animation curves:
        1. Remove redundant keys (linearize holds).
        2. Remove fully static channels.
        
        Args:
            locators: List of locator names
            threshold: Tolerance for considering values as static/equal
        """
        attrs = ["translateX", "translateY", "translateZ",
                 "rotateX", "rotateY", "rotateZ",
                 "scaleX", "scaleY", "scaleZ", "visibility"]
        
        for loc in locators:
            if not cmds.objExists(loc):
                continue
                
            for attr in attrs:
                attr_path = f"{loc}.{attr}"
                
                # Get animation curve
                anim_curve_list = cmds.listConnections(attr_path, type="animCurve")
                if not anim_curve_list:
                    continue
                
                anim_curve = anim_curve_list[0]
                
                # 1. Remove redundancy (optimize curve)
                self.remove_redundant_keys(anim_curve, threshold)
                
                # 2. Check if remaining curve is static
                # Get all keyframe values
                keyframes = cmds.keyframe(anim_curve, query=True, valueChange=True)
                if not keyframes:
                    continue
                
                # Check if all values are essentially the same
                min_val = min(keyframes)
                max_val = max(keyframes)
                
                if (max_val - min_val) <= threshold:
                    # Delete the animation curve (static channel)
                    cmds.delete(anim_curve)

    def remove_redundant_keys(self, anim_curve, threshold=0.001):
        """
        Remove keys that have the same value as their neighbors.
        """
        times = cmds.keyframe(anim_curve, query=True, timeChange=True)
        values = cmds.keyframe(anim_curve, query=True, valueChange=True)
        
        if not times or len(times) < 3:
            return
            
        count = len(times)
        to_delete = []
        
        # Iterate from index 1 to count-2
        for i in range(1, count - 1):
            prev_val = values[i-1]
            curr_val = values[i]
            next_val = values[i+1]
            
            # Check if current roughly equals prev AND next
            if (abs(curr_val - prev_val) <= threshold) and \
               (abs(curr_val - next_val) <= threshold):
                to_delete.append(times[i])
        
        if to_delete:
            cmds.cutKey(anim_curve, time=[(t,t) for t in to_delete])
    
    @staticmethod
    def _locked_axes(node, prefix):
        """
        Return the list of axes ('x','y','z') on `node` whose `<prefix><Axis>`
        attribute is not settable (missing, locked, or already driven by an
        incoming connection). These must be fed to the constraint's `skip`
        flag, otherwise Maya raises an error when it tries to connect to them.
        """
        locked = []
        for axis in ("x", "y", "z"):
            attr = f"{node}.{prefix}{axis.upper()}"
            if not cmds.objExists(attr):
                locked.append(axis)
                continue
            try:
                if not cmds.getAttr(attr, settable=True):
                    locked.append(axis)
            except Exception:
                locked.append(axis)
        return locked

    def rebuild_constraints(self, translate=True, rotate=True, maintain_offset=False):
        """
        Rebuild constraints from locators to source objects.

        Args:
            translate: Apply point constraint
            rotate: Apply orient constraint
            maintain_offset: Maintain offset in constraints

        Channels that are locked or already driven on the source are detected
        and passed via `skip=` so the constraint still succeeds on whatever
        channels remain available.
        """
        for loc_data in self.created_locators:
            source = loc_data["source"]
            locator = loc_data["locator"]

            if not cmds.objExists(source) or not cmds.objExists(locator):
                continue

            if translate:
                skip_t = self._locked_axes(source, "translate")
                if len(skip_t) >= 3:
                    cmds.warning(f"[SpaceSwitch] All translate channels unavailable on '{source}'; skipping pointConstraint.")
                else:
                    kwargs = {"maintainOffset": maintain_offset}
                    if skip_t:
                        kwargs["skip"] = skip_t
                    cmds.pointConstraint(locator, source, **kwargs)

            if rotate:
                skip_r = self._locked_axes(source, "rotate")
                if len(skip_r) >= 3:
                    cmds.warning(f"[SpaceSwitch] All rotate channels unavailable on '{source}'; skipping orientConstraint.")
                else:
                    kwargs = {"maintainOffset": maintain_offset}
                    if skip_r:
                        kwargs["skip"] = skip_r
                    cmds.orientConstraint(locator, source, **kwargs)
    
    def bake_source_animation(self, sources, sample_by=1, euler_filter=True,
                              clean_static=True, threshold=0.001,
                              delete_constraints=False):
        """
        Bake down the source objects' animation keys to capture their current
        motion (driven by locators), and optionally clean up and release.

        Args:
            sources: Iterable of object names to bake.
            sample_by: Bake sample stride.
            euler_filter: Run filterCurve after bake.
            clean_static: Remove redundant / static keys after bake.
            threshold: Tolerance passed to cleanup_keys.
            delete_constraints: If True, remove constraints on each source
                after baking (the "bake and release" flow — leaves clean
                world-space keys with no locator dependency).
        """
        if not sources:
            return

        valid_sources = [s for s in sources if cmds.objExists(s)]
        if not valid_sources:
            return

        start_time = cmds.playbackOptions(query=True, minTime=True)
        end_time   = cmds.playbackOptions(query=True, maxTime=True)

        cmds.refresh(suspend=True)
        try:
            cmds.bakeResults(
                valid_sources,
                simulation=True,
                time=(start_time, end_time),
                sampleBy=sample_by,
                disableImplicitControl=True,
                preserveOutsideKeys=True,
                sparseAnimCurveBake=False,
                minimizeRotation=True,
                controlPoints=False
            )

            if delete_constraints:
                for s in valid_sources:
                    self._delete_constraints_on_node(s)

            if euler_filter:
                cmds.select(valid_sources)
                cmds.filterCurve()

            if clean_static:
                self.cleanup_keys(valid_sources, threshold)

        finally:
            cmds.refresh(suspend=False)

        tag = "released" if delete_constraints else "cleaned"
        print(f"[SpaceSwitch] Baked and {tag} animation on {len(valid_sources)} source(s).")
    
    def cleanup(self, delete_constraints_first=True):
        """
        Clean up locators and constraints.
        Deletes constraints FIRST to prevent objects popping back.
        """
        for loc_data in self.created_locators:
            source = loc_data["source"]
            top_group = loc_data["top_group"]
            master_grp = loc_data.get("master") # Get the master group
            
            if delete_constraints_first and cmds.objExists(source):
                # Delete constraints on source object first
                self._delete_constraints_on_node(source)
            
            # Then delete the locator hierarchy
            # If we delete the master group, everything below it (top_group, locators) goes too.
            if master_grp and cmds.objExists(master_grp):
                cmds.delete(master_grp)
            elif cmds.objExists(top_group):
                # Fallback if master not found for some reason
                cmds.delete(top_group)
        
        self.created_locators = []
    
    def _delete_constraints_on_node(self, node):
        """Delete all constraints on a given node."""
        constraint_types = [
            "pointConstraint", "orientConstraint", "scaleConstraint",
            "parentConstraint", "aimConstraint"
        ]
        
        for ctype in constraint_types:
            constraints = cmds.listRelatives(node, type=ctype) or []
            for c in constraints:
                if cmds.objExists(c):
                    cmds.delete(c)

# ============================================================================
# DASHBOARD UI  (PySide2 / Qt — cyberpunk theme)
# ============================================================================
class SpaceSwitchDashboard(QtWidgets.QWidget):
    """PySide2 dashboard for the Space Switch tool — cyberpunk theme."""

    def __init__(self, parent=None):
        super(SpaceSwitchDashboard, self).__init__(parent, QtCore.Qt.Window)
        self.switcher = SpaceSwitcher()
        self.preview_locator = None
        self.target_object = None
        self.source_objects = []
        self.settings = {
            "space_mode": "world",
            "translate": True,
            "rotate": True,
            "aim_at_target": False,
            "rotation_order": 0,
            "locator_size": 1,
            "hide_offset_locators": True,
            "bake_master_space": False,
            "bake_master_layer": False,
            "bake_offset_layer": False,
            "keep_target_tether": True,
            "create_target_locator": False,
            "add_to_display_layer": False,
            "num_offsets": 2,
            "color_index": 17,
            "sample_by": 1,
            "euler_filter": True,
            "clean_static": True,
            "static_threshold": 0.001,
            "auto_best_order": True,
        }
        self._fade_anim = None
        self.baking_counter = 0
        self.status_timer = QtCore.QTimer()
        self.status_timer.timeout.connect(self._update_status_anim)
        self.build_ui()
    
    # =========================================================================
    # ANIMATION / SHOW
    # =========================================================================
    def showEvent(self, event):
        """Fade the window in on first show only (not on restore/activate)."""
        if not getattr(self, "_faded_in", False):
            self.setWindowOpacity(0.0)
            self._fade_anim = QtCore.QPropertyAnimation(self, b"windowOpacity")
            self._fade_anim.setDuration(800)
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            self._fade_anim.start()
            self._faded_in = True
        super(SpaceSwitchDashboard, self).showEvent(event)

    def _set_status(self, msg, animated=False):
        """Update the status bar. Pass animated=True while baking."""
        if animated:
            self.baking_counter = 0
            self.status_timer.start(300)
        else:
            self.status_timer.stop()
            self.status_label.setText(msg)

    def _update_status_anim(self):
        self.baking_counter = (self.baking_counter + 1) % 4
        dots = "·" * self.baking_counter + "  " * (3 - self.baking_counter)
        self.status_label.setText(f"◈  BAKING{dots}")

    # =========================================================================
    # BUILD UI
    # =========================================================================
    def build_ui(self):
        """Build the PySide2 dashboard UI."""
        # Delete preview locator if exists
        if cmds.objExists("_SS_preview_locator"):
            cmds.delete("_SS_preview_locator")
        
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(360)
        self.resize(400, 740)
        self.setStyleSheet(CYBERPUNK_SS)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        header = QtWidgets.QFrame()
        header_layout = QtWidgets.QVBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 8)
        header_layout.setSpacing(2)
        title_lbl = QtWidgets.QLabel("◈  SPACE  SWITCH")
        sub_lbl   = QtWidgets.QLabel("ANIMATOR DASHBOARD  v2.0")
        header_layout.addWidget(title_lbl)
        header_layout.addWidget(sub_lbl)
        header.setStyleSheet("""
            QFrame {
                background-color: #0A0A1E;
                border-bottom: 2px solid #4DD0E1;
            }
            QLabel { background-color: transparent; }
        """)
        title_lbl.setStyleSheet("color:#4DD0E1; font-size:16px; font-weight:bold; letter-spacing:3px;")
        sub_lbl.setStyleSheet("color:#546E7A; font-size:9px; letter-spacing:2px;")
        outer.addWidget(header)

        # ── Status bar ──────────────────────────────────────────────────────
        self.status_label = QtWidgets.QLabel("◈  READY")
        self.status_label.setStyleSheet(
            "background-color:#0A0A1E; color:#4DD0E1; font-size:10px;"
            " padding:4px 12px; border-bottom:1px solid #2E4A5A;"
        )
        outer.addWidget(self.status_label)

        # ── Scrollable content ───────────────────────────────────────────────
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        content_widget = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(content_widget)
        self.content_layout.setSpacing(8)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        scroll.setWidget(content_widget)
        outer.addWidget(scroll)

        self._build_space_mode_section()
        self._build_attributes_section()
        self._build_locator_settings_section()
        self._build_bake_options_section()
        self._build_workflow_section()
        self._build_finalize_section()
        self._build_cleanup_section()

        self.content_layout.addStretch()

        # Pre-populate source field from current Maya selection
        sel = cmds.ls(selection=True)
        if sel:
            self.source_objects = list(sel)
            display_text = ", ".join(sel) if len(sel) <= 3 else f"{sel[0]} ... ({len(sel)} objects)"
            self.source_field.setText(display_text)


    # =========================================================================
    # SECTION BUILDERS
    # =========================================================================
    @staticmethod
    def _make_section(title):
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 14, 8, 8)
        box.setLayout(layout)
        return box, layout

    @staticmethod
    def _hrow(parent_layout, spacing=6):
        row = QtWidgets.QWidget()
        hl = QtWidgets.QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(spacing)
        parent_layout.addWidget(row)
        return hl

    @staticmethod
    def _sep(parent_layout):
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet("QFrame { color: #2E4A5A; }")
        parent_layout.addWidget(line)

    def _build_space_mode_section(self):
        box, layout = self._make_section("SPACE MODE")

        # Mode radio buttons
        self.mode_group = QtWidgets.QButtonGroup(self)
        r1 = self._hrow(layout, spacing=12)
        self.rb_world  = QtWidgets.QRadioButton("World");  self.rb_world.setChecked(True)
        self.rb_local  = QtWidgets.QRadioButton("Local")
        self.rb_object = QtWidgets.QRadioButton("Object")
        for rb in (self.rb_world, self.rb_local, self.rb_object):
            self.mode_group.addButton(rb); r1.addWidget(rb)
        r1.addStretch()

        r2 = self._hrow(layout, spacing=12)
        self.rb_camera = QtWidgets.QRadioButton("Camera")
        self.rb_aim    = QtWidgets.QRadioButton("Aim")
        for rb in (self.rb_camera, self.rb_aim):
            self.mode_group.addButton(rb); r2.addWidget(rb)
        r2.addStretch()

        self.rb_world.toggled.connect( lambda c: c and self._on_space_mode_change("world"))
        self.rb_local.toggled.connect( lambda c: c and self._on_space_mode_change("local"))
        self.rb_object.toggled.connect(lambda c: c and self._on_space_mode_change("object"))
        self.rb_camera.toggled.connect(lambda c: c and self._on_space_mode_change("camera"))
        self.rb_aim.toggled.connect(   lambda c: c and self._on_space_mode_change("aim"))

        self._sep(layout)

        # Source row
        rs = self._hrow(layout)
        rs.addWidget(QtWidgets.QLabel("Source:"))
        self.source_field = QtWidgets.QLineEdit()
        self.source_field.setPlaceholderText("Pick or select objects…")
        self.source_field.setReadOnly(True)
        rs.addWidget(self.source_field, 1)
        src_pick = QtWidgets.QPushButton("PICK")
        src_pick.setFixedWidth(52)
        src_pick.clicked.connect(lambda: self._pick_object("source"))
        rs.addWidget(src_pick)

        # Target row
        rt = self._hrow(layout)
        rt.addWidget(QtWidgets.QLabel("Target: "))
        self.target_field = QtWidgets.QLineEdit()
        self.target_field.setPlaceholderText("Object / camera / aim target…")
        rt.addWidget(self.target_field, 1)
        tgt_pick = QtWidgets.QPushButton("PICK")
        tgt_pick.setFixedWidth(52)
        tgt_pick.clicked.connect(lambda: self._pick_object("target"))
        rt.addWidget(tgt_pick)

        # Object-mode toggles
        ro = self._hrow(layout, spacing=10)
        self.chk_keep_tether = QtWidgets.QCheckBox("Keep Target Tether")
        self.chk_keep_tether.setChecked(True)
        self.chk_keep_tether.setToolTip(
            "Object mode: preserve master→target parentConstraint after baking "
            "so moving the target drags the source stack.")
        self.chk_keep_tether.toggled.connect(
            lambda v: self._update_setting("keep_target_tether", v))
        self.chk_create_tgt_loc = QtWidgets.QCheckBox("Create Target Locator")
        self.chk_create_tgt_loc.setChecked(False)
        self.chk_create_tgt_loc.setToolTip(
            "Object mode: also build a locator setup for the target so its own "
            "locator drives it (symmetric with source).")
        self.chk_create_tgt_loc.toggled.connect(
            lambda v: self._update_setting("create_target_locator", v))
        ro.addWidget(self.chk_keep_tether)
        ro.addWidget(self.chk_create_tgt_loc)
        ro.addStretch()

        self.content_layout.addWidget(box)

    def _build_attributes_section(self):
        box, layout = self._make_section("ATTRIBUTES")

        r1 = self._hrow(layout, spacing=12)
        self.chk_translate = QtWidgets.QCheckBox("Translation")
        self.chk_translate.setChecked(True)
        self.chk_translate.toggled.connect(lambda v: self._update_setting("translate", v))
        self.chk_rotate = QtWidgets.QCheckBox("Rotation")
        self.chk_rotate.setChecked(True)
        self.chk_rotate.toggled.connect(lambda v: self._update_setting("rotate", v))
        r1.addWidget(self.chk_translate)
        r1.addWidget(self.chk_rotate)
        r1.addStretch()

        r2 = self._hrow(layout, spacing=6)
        r2.addWidget(QtWidgets.QLabel("Rotation Order:"))
        self.rot_order_combo = QtWidgets.QComboBox()
        for ro in ROTATION_ORDERS:
            self.rot_order_combo.addItem(ro.upper())
        self.rot_order_combo.currentTextChanged.connect(self._on_rotation_order_change)
        r2.addWidget(self.rot_order_combo)
        self.chk_auto_order = QtWidgets.QCheckBox("Auto-Detect")
        self.chk_auto_order.setChecked(True)
        self.chk_auto_order.setToolTip(
            "Automatically calculate best rotation order to avoid gimbal lock.")
        self.chk_auto_order.toggled.connect(lambda v: self._update_setting("auto_best_order", v))
        r2.addWidget(self.chk_auto_order)
        r2.addStretch()

        self.content_layout.addWidget(box)

    def _build_locator_settings_section(self):
        box, layout = self._make_section("LOCATOR SETTINGS")

        prev_btn = QtWidgets.QPushButton("Create Preview Locator")
        prev_btn.clicked.connect(self._create_preview_locator)
        layout.addWidget(prev_btn)

        # Scale row
        rs = self._hrow(layout, spacing=4)
        rs.addWidget(QtWidgets.QLabel("Scale:"))
        minus_btn = QtWidgets.QPushButton("−")
        minus_btn.setFixedWidth(32)
        minus_btn.setToolTip("Divide locator scale by factor")
        minus_btn.clicked.connect(lambda: self._adj_scale(False))
        rs.addWidget(minus_btn)
        plus_btn = QtWidgets.QPushButton("+")
        plus_btn.setFixedWidth(32)
        plus_btn.setToolTip("Multiply locator scale by factor")
        plus_btn.clicked.connect(lambda: self._adj_scale(True))
        rs.addWidget(plus_btn)
        self.scale_factor_field = QtWidgets.QDoubleSpinBox()
        self.scale_factor_field.setValue(1.5)
        self.scale_factor_field.setDecimals(2)
        self.scale_factor_field.setRange(0.01, 999.0)
        self.scale_factor_field.setFixedWidth(68)
        self.scale_factor_field.setToolTip("Multiplication / division factor")
        rs.addWidget(self.scale_factor_field)
        rs.addStretch()

        # Offsets row
        ro = self._hrow(layout, spacing=6)
        ro.addWidget(QtWidgets.QLabel("Offsets:"))
        self.offset_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.offset_slider.setRange(1, 5)
        self.offset_slider.setValue(2)
        self.offset_spinbox = QtWidgets.QSpinBox()
        self.offset_spinbox.setRange(1, 5)
        self.offset_spinbox.setValue(2)
        self.offset_spinbox.setFixedWidth(42)
        self.offset_slider.valueChanged.connect(self.offset_spinbox.setValue)
        self.offset_slider.valueChanged.connect(
            lambda v: self._update_setting("num_offsets", v))
        self.offset_spinbox.valueChanged.connect(self.offset_slider.setValue)
        ro.addWidget(self.offset_slider, 1)
        ro.addWidget(self.offset_spinbox)
        self.chk_hide_offset = QtWidgets.QCheckBox("Hide Offset")
        self.chk_hide_offset.setChecked(True)
        self.chk_hide_offset.setToolTip("Hide offset locator shape by default.")
        self.chk_hide_offset.toggled.connect(
            lambda v: self._update_setting("hide_offset_locators", v))
        ro.addWidget(self.chk_hide_offset)

        # Color swatches
        layout.addWidget(QtWidgets.QLabel("Locator Color:"))
        rc = self._hrow(layout, spacing=3)
        color_swatches = [
            ("red",    "#CC3333"), ("yellow", "#CCCC33"),
            ("green",  "#33CC33"), ("blue",   "#3366CC"),
            ("purple", "#9933CC"), ("white",  "#CCCCCC"),
            ("cyan",   "#33CCCC"), ("orange", "#CC7722"),
        ]
        for name, hex_col in color_swatches:
            btn = QtWidgets.QPushButton()
            btn.setFixedSize(28, 22)
            btn.setToolTip(name.title())
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_col};
                    border: 1px solid #555;
                    border-radius: 2px;
                    padding: 0;
                }}
                QPushButton:hover {{ border: 2px solid #4DD0E1; }}
            """)
            btn.clicked.connect(lambda checked=False, n=name: self._on_color_select(n))
            rc.addWidget(btn)
        rc.addStretch()

        self.chk_display_layer = QtWidgets.QCheckBox("Add to Display Layer")
        self.chk_display_layer.setChecked(False)
        self.chk_display_layer.setToolTip("Add offset locators to a display layer.")
        self.chk_display_layer.toggled.connect(
            lambda v: self._update_setting("add_to_display_layer", v))
        layout.addWidget(self.chk_display_layer)

        self.content_layout.addWidget(box)

    def _build_bake_options_section(self):
        box, layout = self._make_section("BAKE OPTIONS")

        r1 = self._hrow(layout, spacing=6)
        r1.addWidget(QtWidgets.QLabel("Sample By:"))
        self.sample_combo = QtWidgets.QComboBox()
        for v in ("1", "2", "5", "10"):
            self.sample_combo.addItem(v)
        self.sample_combo.currentTextChanged.connect(
            lambda v: self._update_setting("sample_by", int(v)))
        r1.addWidget(self.sample_combo)
        self.chk_euler = QtWidgets.QCheckBox("Euler Filter")
        self.chk_euler.setChecked(True)
        self.chk_euler.toggled.connect(lambda v: self._update_setting("euler_filter", v))
        r1.addWidget(self.chk_euler)
        r1.addStretch()

        r2 = self._hrow(layout, spacing=6)
        self.chk_clean_static = QtWidgets.QCheckBox("Clean Static Keys")
        self.chk_clean_static.setChecked(True)
        self.chk_clean_static.toggled.connect(
            lambda v: self._update_setting("clean_static", v))
        r2.addWidget(self.chk_clean_static)
        r2.addWidget(QtWidgets.QLabel("Threshold:"))
        self.threshold_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_spin.setDecimals(4)
        self.threshold_spin.setValue(0.001)
        self.threshold_spin.setSingleStep(0.0001)
        self.threshold_spin.setRange(0.0, 1.0)
        self.threshold_spin.setFixedWidth(78)
        self.threshold_spin.valueChanged.connect(
            lambda v: self._update_setting("static_threshold", v))
        r2.addWidget(self.threshold_spin)
        r2.addStretch()

        self.chk_bake_master = QtWidgets.QCheckBox("Bake Master Space")
        self.chk_bake_master.setChecked(False)
        self.chk_bake_master.setToolTip(
            "Bake the Master Group to curves and delete its constraints before baking locators.")
        self.chk_bake_master.toggled.connect(
            lambda v: self._update_setting("bake_master_space", v))
        layout.addWidget(self.chk_bake_master)

        r3 = self._hrow(layout, spacing=10)
        self.chk_master_layer = QtWidgets.QCheckBox("Master → Anim Layer")
        self.chk_master_layer.setChecked(False)
        self.chk_master_layer.setToolTip(
            "If baking master space, put animation on 'Master_Space_AnimLayer'.")
        self.chk_master_layer.toggled.connect(
            lambda v: self._update_setting("bake_master_layer", v))
        self.chk_offset_layer = QtWidgets.QCheckBox("Offset → Anim Layer")
        self.chk_offset_layer.setChecked(False)
        self.chk_offset_layer.setToolTip("Put offset locator animation on 'Offset_AnimLayer'.")
        self.chk_offset_layer.toggled.connect(
            lambda v: self._update_setting("bake_offset_layer", v))
        r3.addWidget(self.chk_master_layer)
        r3.addWidget(self.chk_offset_layer)
        r3.addStretch()

        self.content_layout.addWidget(box)

    def _build_workflow_section(self):
        box, layout = self._make_section("WORKFLOW STAGES")

        rw = self._hrow(layout, spacing=6)
        self.stage_menu = QtWidgets.QComboBox()
        self.stage_menu.addItem("STAGE 1: Create Setup")
        self.stage_menu.addItem("STAGE 2: Bake to Locators")
        self.stage_menu.addItem("STAGE 3: Rebuild Constraints")
        rw.addWidget(self.stage_menu, 1)
        run_stage_btn = QtWidgets.QPushButton("RUN")
        run_stage_btn.setFixedWidth(58)
        run_stage_btn.clicked.connect(self._run_selected_stage)
        rw.addWidget(run_stage_btn)

        self.content_layout.addWidget(box)

        # Big full-run button (lives outside the groupbox for visual weight)
        run_all_btn = QtWidgets.QPushButton("◈  RUN FULL SPACE SWITCH")
        run_all_btn.setMinimumHeight(46)
        run_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #0D5966;
                border: 2px solid #4DD0E1;
                color: #E0E0E0;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 2px;
                padding: 10px;
                border-radius: 4px;
                font-family: "Courier New", monospace;
            }
            QPushButton:hover {
                background-color: #4DD0E1;
                color: #0A0A1E;
            }
            QPushButton:pressed { background-color: #00BCD4; color: #0A0A1E; }
        """)
        run_all_btn.clicked.connect(self._stage_run_all)
        self.content_layout.addWidget(run_all_btn)

    def _build_finalize_section(self):
        box, layout = self._make_section("FINALIZE")
        bake_btn = QtWidgets.QPushButton("BAKE SOURCES DOWN")
        bake_btn.setToolTip(
            "Bake driven sources to clean keys, run Euler filter, and remove constraints.")
        bake_btn.setStyleSheet("""
            QPushButton {
                background-color: #2E1A0A;
                border: 1px solid #FFB74D;
                color: #FFB74D;
                font-weight: bold;
                padding: 6px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #FFB74D; color: #1A1A2E; }
            QPushButton:pressed { background-color: #FFA726; }
        """)
        bake_btn.clicked.connect(self._bake_sources_down)
        layout.addWidget(bake_btn)
        self.content_layout.addWidget(box)

    def _build_cleanup_section(self):
        box, layout = self._make_section("CLEANUP")
        rc = self._hrow(layout, spacing=6)

        sel_btn = QtWidgets.QPushButton("Select Locators")
        sel_btn.clicked.connect(self._select_locators)
        rc.addWidget(sel_btn, 1)

        del_btn = QtWidgets.QPushButton("Delete All")
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: #2E0A0A;
                border: 1px solid #FF5252;
                color: #FF5252;
                font-weight: bold;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #FF5252; color: #1A1A2E; }
            QPushButton:pressed { background-color: #E53935; }
        """)
        del_btn.clicked.connect(self._cleanup_all)
        rc.addWidget(del_btn, 1)

        self.content_layout.addWidget(box)

    # =========================================================================
    # UI CALLBACKS
    # =========================================================================
    def _update_setting(self, key, value):
        self.settings[key] = value

    def _on_space_mode_change(self, mode):
        self.settings["space_mode"] = mode
        if mode == "camera":
            panel = cmds.getPanel(withFocus=True)
            if panel and "modelPanel" in panel:
                cam = cmds.modelPanel(panel, query=True, camera=True)
                if cam:
                    if cmds.nodeType(cam) == "camera":
                        cam = cmds.listRelatives(cam, parent=True)[0]
                    self.target_field.setText(cam)
                    self.target_object = cam

    def _on_rotation_order_change(self, value):
        try:
            order_index = ROTATION_ORDERS.index(value.lower())
        except ValueError:
            return
        self.settings["rotation_order"] = order_index
        if self.preview_locator and cmds.objExists(self.preview_locator):
            cmds.setAttr(f"{self.preview_locator}.rotateOrder", order_index)

    def _adj_scale(self, multiply=True):
        factor = self.scale_factor_field.value()
        if factor <= 0:
            cmds.warning("Scale factor must be positive.")
            return
        sel = cmds.ls(selection=True)
        if not sel and self.preview_locator and cmds.objExists(self.preview_locator):
            target_objs = [self.preview_locator]
        else:
            target_objs = sel
        if not target_objs:
            cmds.warning("Select locators/objects to scale.")
            return
        scale_mult = factor if multiply else 1.0 / factor
        for obj in target_objs:
            if cmds.getAttr(f"{obj}.scaleX", lock=True):
                continue
            shapes = cmds.listRelatives(obj, shapes=True)
            if shapes and cmds.nodeType(shapes[0]) == "locator":
                shape = shapes[0]
                sx = cmds.getAttr(f"{shape}.localScaleX")
                new_s = max(0.001, sx * scale_mult)
                cmds.setAttr(f"{shape}.localScaleX", new_s)
                cmds.setAttr(f"{shape}.localScaleY", new_s)
                cmds.setAttr(f"{shape}.localScaleZ", new_s)
            else:
                current_x = cmds.getAttr(f"{obj}.scaleX")
                new_s = max(0.001, current_x * scale_mult)
                cmds.scale(new_s, new_s, new_s, obj)

    def _on_color_select(self, color_name):
        color_index = LOCATOR_COLORS.get(color_name, 17)
        self.settings["color_index"] = color_index
        sel = cmds.ls(selection=True)
        if not sel and self.preview_locator and cmds.objExists(self.preview_locator):
            sel = [self.preview_locator]
        if not sel:
            cmds.inViewMessage(
                message=f"Color set to {color_name}. Select objects to apply.",
                pos="midCenter", fade=True)
            return
        for obj in sel:
            shapes = cmds.listRelatives(obj, shapes=True)
            if not shapes:
                continue
            for shape in shapes:
                cmds.setAttr(f"{shape}.overrideEnabled", 1)
                cmds.setAttr(f"{shape}.overrideColor", color_index)

    def _pick_object(self, field_type):
        sel = cmds.ls(selection=True)
        if not sel:
            cmds.warning("Nothing selected to pick.")
            return
        if field_type == "source":
            self.source_objects = list(sel)
            if len(sel) == 1:
                display_text = sel[0]
            elif len(sel) <= 3:
                display_text = ", ".join(sel)
            else:
                display_text = f"{sel[0]} ... ({len(sel)} objects)"
            self.source_field.setText(display_text)
        elif field_type == "target":
            self.target_object = sel[0]
            self.target_field.setText(sel[0])

    def _create_preview_locator(self):
        if cmds.objExists("_SS_preview_locator"):
            cmds.delete("_SS_preview_locator")
        source_obj = self.source_field.text().strip()
        if not source_obj or not cmds.objExists(source_obj):
            sel = cmds.ls(selection=True)
            if sel:
                source_obj = sel[0]
        loc = cmds.spaceLocator(name="_SS_preview_locator")[0]
        self.preview_locator = loc
        size = self.settings["locator_size"]
        cmds.setAttr(f"{loc}.localScaleX", size)
        cmds.setAttr(f"{loc}.localScaleY", size)
        cmds.setAttr(f"{loc}.localScaleZ", size)
        shape = cmds.listRelatives(loc, shapes=True)[0]
        cmds.setAttr(f"{shape}.overrideEnabled", 1)
        cmds.setAttr(f"{shape}.overrideColor", self.settings["color_index"])
        cmds.setAttr(f"{loc}.rotateOrder", self.settings["rotation_order"])
        if source_obj and cmds.objExists(source_obj):
            cmds.matchTransform(loc, source_obj, position=True, rotation=True)
        cmds.select(loc)

    # =========================================================================
    # STAGE OPERATIONS
    # =========================================================================
    def _stage_create(self, *args):
        """Stage 1: Create locator setup for all source objects."""
        objects_to_process = list(self.source_objects) if self.source_objects else []
        if not objects_to_process:
            sel = cmds.ls(selection=True)
            if sel:
                objects_to_process = list(sel)
                self.source_objects = list(sel)
                if len(sel) == 1:
                    display_text = sel[0]
                elif len(sel) <= 3:
                    display_text = ", ".join(sel)
                else:
                    display_text = f"{sel[0]} ... ({len(sel)} objects)"
                self.source_field.setText(display_text)

        objects_to_process = [obj for obj in objects_to_process if cmds.objExists(obj)]
        if not objects_to_process:
            cmds.warning("Please pick source object(s) or select objects.")
            return False

        print(f"Processing {len(objects_to_process)} source object(s): {objects_to_process}")

        if cmds.objExists("_SS_preview_locator"):
            cmds.delete("_SS_preview_locator")
            self.preview_locator = None

        self.switcher = SpaceSwitcher()

        effective_mode = self.settings.get("space_mode", "world")
        if effective_mode in ["object", "camera", "aim"]:
            target_obj_name = self.target_field.text().strip()
            if not target_obj_name or not cmds.objExists(target_obj_name):
                cmds.warning(f"{effective_mode.title()} mode requires a valid Target object.")
                return False
            self.target_object = target_obj_name

        for obj in objects_to_process:
            rot_order = self.settings["rotation_order"]
            if self.settings["auto_best_order"]:
                start = cmds.playbackOptions(q=True, min=True)
                end   = cmds.playbackOptions(q=True, max=True)
                best  = self.switcher.get_best_rotation_order(obj, start, end)
                if best is not None:
                    rot_order = best

            top_group, locator, master = self.switcher.create_locator_hierarchy(
                source_obj=obj,
                target_obj=self.target_object,
                mode=effective_mode,
                num_offsets=self.settings["num_offsets"],
                locator_size=self.settings["locator_size"],
                color_index=self.settings["color_index"],
                rotation_order=rot_order,
                hide_offset=self.settings.get("hide_offset_locators", True)
            )
            if not top_group:
                continue

            self.switcher.create_temp_constraints(
                obj, top_group,
                translate=self.settings["translate"],
                rotate=self.settings["rotate"]
            )

            if cmds.objExists("rig_layer"):
                cmds.editDisplayLayerMembers("rig_layer", master, noRecurse=True)

            if self.settings["add_to_display_layer"]:
                base_name = self._get_base_name(obj)
                self._add_to_display_layer([master],          f"{base_name}_Master_DL", color=13)
                self._add_to_display_layer([locator, top_group], f"{base_name}_Offset_DL", color=6)

        # Optional target-locator setup (Object mode only)
        if (effective_mode == "object"
                and self.settings.get("create_target_locator", False)
                and self.target_object
                and cmds.objExists(self.target_object)):
            target  = self.target_object
            t_rot   = self.settings["rotation_order"]
            if self.settings["auto_best_order"]:
                start = cmds.playbackOptions(q=True, min=True)
                end   = cmds.playbackOptions(q=True, max=True)
                best  = self.switcher.get_best_rotation_order(target, start, end)
                if best is not None:
                    t_rot = best

            t_top, t_loc, t_master = self.switcher.create_locator_hierarchy(
                source_obj=target,
                target_obj=None,
                mode="world",
                num_offsets=self.settings["num_offsets"],
                locator_size=self.settings["locator_size"],
                color_index=self.settings["color_index"],
                rotation_order=t_rot,
                hide_offset=self.settings.get("hide_offset_locators", True)
            )
            if t_top:
                self.switcher.created_locators[-1]["is_target_setup"] = True
                self.switcher.create_temp_constraints(
                    target, t_top,
                    translate=self.settings["translate"],
                    rotate=self.settings["rotate"]
                )
                if cmds.objExists("rig_layer"):
                    cmds.editDisplayLayerMembers("rig_layer", t_master, noRecurse=True)
                if self.settings["add_to_display_layer"]:
                    t_base = self._get_base_name(target)
                    self._add_to_display_layer([t_master],          f"{t_base}_Master_DL", color=13)
                    self._add_to_display_layer([t_loc, t_top], f"{t_base}_Offset_DL",  color=6)

        top_groups = [data["top_group"] for data in self.switcher.created_locators]
        cmds.select(top_groups)
        self._set_status(f"◈  CREATED {len(top_groups)} SETUP(S)")
        QtCore.QTimer.singleShot(3000, lambda: self._set_status("◈  READY"))
        cmds.inViewMessage(
            message=f"Created {len(top_groups)} locator setup(s). Ready for baking.",
            pos="midCenter", fade=True)
        return True

    def _stage_bake(self, *args):
        """Stage 2: Bake animation to locators."""
        if not self.switcher.created_locators:
            cmds.warning("No locators to bake. Run Stage 1 first.")
            return False

        self._set_status("◈  BAKING", animated=True)
        QtWidgets.QApplication.processEvents()

        sample_by    = self.settings["sample_by"]
        euler_filter = self.settings["euler_filter"]

        grouped_data = {}
        for data in self.switcher.created_locators:
            base = self._get_base_name(data["source"])
            grouped_data.setdefault(base, []).append(data)

        # Phase 1: optionally bake masters
        keep_tether        = self.settings.get("keep_target_tether", True)
        should_bake_master = self.settings.get("bake_master_space", False) and not keep_tether
        if should_bake_master:
            all_masters = [d["master"] for d in self.switcher.created_locators
                           if not d.get("is_target_setup", False)]
            if self.settings["bake_master_layer"]:
                for base_name, data_list in grouped_data.items():
                    grp_masters = [d["master"] for d in data_list
                                   if not d.get("is_target_setup", False)]
                    if not grp_masters:
                        continue
                    layer = self._get_or_create_anim_layer(f"{base_name}_Master_AL")
                    if layer:
                        cmds.select(grp_masters)
                        cmds.animLayer(layer, edit=True, addSelectedObjects=True)
            self.switcher.bake_animation(
                all_masters, sample_by=sample_by, euler_filter=euler_filter,
                cleanup_constraints=False, destination_layer=None)
            for master in all_masters:
                self.switcher._delete_constraints_on_node(master)

        # Phase 2: bake all top_groups
        all_top_groups = [d["top_group"] for d in self.switcher.created_locators]
        if self.settings["bake_offset_layer"]:
            for base_name, data_list in grouped_data.items():
                grp_tops = [d["top_group"] for d in data_list]
                layer = self._get_or_create_anim_layer(f"{base_name}_Offset_AL")
                if layer:
                    cmds.select(grp_tops)
                    cmds.animLayer(layer, edit=True, addSelectedObjects=True)
        self.switcher.bake_animation(
            all_top_groups, sample_by=sample_by, euler_filter=euler_filter,
            cleanup_constraints=True, destination_layer=None)

        # Phase 3: clean static keys
        if self.settings["clean_static"]:
            for base_name, data_list in grouped_data.items():
                self.switcher.cleanup_keys(
                    [d["top_group"] for d in data_list],
                    self.settings["static_threshold"])

        locators = [d["locator"] for d in self.switcher.created_locators]
        cmds.select(locators)
        self._set_status(f"◈  BAKED {len(all_top_groups)} LOCATOR(S)")
        QtCore.QTimer.singleShot(3000, lambda: self._set_status("◈  READY"))
        cmds.inViewMessage(
            message=f"Baked {len(all_top_groups)} locator(s). Ready for adjustments.",
            pos="midCenter", fade=True)
        return True

    def _stage_rebuild(self, *args):
        """Stage 3: Apply locator -> source constraints."""
        if not self.switcher.created_locators:
            cmds.warning("No locator data. Run Stage 1 and 2 first.")
            return False
        self.switcher.rebuild_constraints(
            translate=self.settings["translate"],
            rotate=self.settings["rotate"],
            maintain_offset=False)
        sources = [data["source"] for data in self.switcher.created_locators]
        cmds.select(sources)
        self._set_status("◈  REBUILD COMPLETE")
        QtCore.QTimer.singleShot(3000, lambda: self._set_status("◈  READY"))
        cmds.inViewMessage(
            message="Stage 3 complete. Sources are now driven by locators.",
            pos="midCenter", fade=True)
        return True

    def _stage_run_all(self, *args):
        """Run all 3 stages in sequence."""
        current_frame = cmds.currentTime(query=True)
        if not self._stage_create():
            return
        cmds.refresh()
        if not self._stage_bake():
            return
        if not self._stage_rebuild():
            return
        cmds.currentTime(current_frame)
        if self.switcher.created_locators:
            top_groups = [d["top_group"] for d in self.switcher.created_locators
                          if cmds.objExists(d["top_group"])]
            if top_groups:
                cmds.select(top_groups)
        self._set_status("◈  SPACE SWITCH COMPLETE")
        QtCore.QTimer.singleShot(4000, lambda: self._set_status("◈  READY"))
        cmds.inViewMessage(
            message="FULL SPACE SWITCH COMPLETE!  Offset locators selected.",
            pos="midCenter", fade=True)

    def _run_selected_stage(self, *args):
        selection = self.stage_menu.currentText()
        if "STAGE 1" in selection:
            self._stage_create()
        elif "STAGE 2" in selection:
            self._stage_bake()
        elif "STAGE 3" in selection:
            self._stage_rebuild()

    def _bake_sources_down(self, *args):
        if not self.switcher.created_locators:
            cmds.warning("No locator data. Run the Space Switch process first.")
            return
        sources = [d["source"] for d in self.switcher.created_locators
                   if cmds.objExists(d["source"])]
        if not sources:
            cmds.warning("No valid sources found to bake.")
            return
        self._set_status("◈  BAKING SOURCES", animated=True)
        QtWidgets.QApplication.processEvents()
        self.switcher.bake_source_animation(
            sources,
            sample_by=self.settings["sample_by"],
            euler_filter=self.settings["euler_filter"],
            clean_static=self.settings["clean_static"],
            threshold=self.settings["static_threshold"],
            delete_constraints=True)
        cmds.select(sources)
        self._set_status("◈  SOURCES BAKED DOWN")
        QtCore.QTimer.singleShot(3000, lambda: self._set_status("◈  READY"))
        cmds.inViewMessage(
            message="Sources baked down and filtered. Constraints removed.",
            pos="midCenter", fade=True)

    # =========================================================================
    # CLEANUP
    # =========================================================================
    def _select_locators(self, *args):
        if self.switcher.created_locators:
            locators = [d["top_group"] for d in self.switcher.created_locators]
            existing = [l for l in locators if cmds.objExists(l)]
            if existing:
                cmds.select(existing)
            else:
                cmds.warning("No locators found in scene.")
        else:
            all_locs = cmds.ls("*" + LOCATOR_SUFFIX, type="transform")
            if all_locs:
                cmds.select(all_locs)
            else:
                cmds.warning("No space switch locators found.")

    def _cleanup_all(self, *args):
        layers_to_delete = set()
        if self.switcher.created_locators:
            for data in self.switcher.created_locators:
                base_name = self._get_base_name(data["source"])
                layers_to_delete.update([
                    f"{base_name}_Master_DL", f"{base_name}_Offset_DL",
                    f"{base_name}_Master_AL", f"{base_name}_Offset_AL",
                ])
        for layer in layers_to_delete:
            if cmds.objExists(layer):
                try:
                    cmds.delete(layer)
                except Exception as e:
                    print(f"Could not delete layer {layer}: {e}")
        self.switcher.cleanup(delete_constraints_first=True)
        if cmds.objExists("_SS_preview_locator"):
            cmds.delete("_SS_preview_locator")
        self._set_status("◈  CLEANUP COMPLETE")
        QtCore.QTimer.singleShot(3000, lambda: self._set_status("◈  READY"))
        cmds.inViewMessage(
            message="Cleanup complete. Layers, constraints, and locators deleted.",
            pos="midCenter", fade=True)

    # =========================================================================
    # UTILITIES
    # =========================================================================
    def _get_base_name(self, node_name):
        short_name = node_name.split(":")[-1].split("|")[-1]
        if short_name.lower().endswith("_ctl"):
            return short_name[:-4]
        return short_name

    def _add_to_display_layer(self, nodes, layer_name="SpaceSwitch_Layer", color=None):
        if not cmds.objExists(layer_name):
            cmds.createDisplayLayer(name=layer_name, empty=True)
            cmds.setAttr(f"{layer_name}.displayType", 0)
            if color is not None:
                cmds.setAttr(f"{layer_name}.color", color)
        cmds.editDisplayLayerMembers(layer_name, nodes, noRecurse=False)

    def _get_or_create_anim_layer(self, layer_name):
        if not cmds.objExists(layer_name):
            return cmds.animLayer(layer_name)
        return layer_name


# ============================================================================
# LAUNCH
# ============================================================================
_space_switch_ui_instance = None

def show():
    """Show the Space Switch Dashboard (creates or re-raises the window)."""
    global _space_switch_ui_instance
    # Close any existing instance cleanly
    if _space_switch_ui_instance is not None:
        try:
            _space_switch_ui_instance.close()
            _space_switch_ui_instance.deleteLater()
        except Exception:
            pass
    parent = _maya_main_window()
    _space_switch_ui_instance = SpaceSwitchDashboard(parent=parent)
    _space_switch_ui_instance.show()
    _space_switch_ui_instance.raise_()
    _space_switch_ui_instance.activateWindow()
    return _space_switch_ui_instance


# Run on Script Editor paste (execbuffer runs as __main__).
# Importing as a module will NOT auto-show — callers must invoke show() themselves.
if __name__ == "__main__":
    show()
