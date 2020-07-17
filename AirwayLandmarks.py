import os
import unittest
import vtk, qt, ctk, slicer
import re
import numpy as np
from slicer.ScriptedLoadableModule import *
import logging
import json

#
# Airway Landmarks
#

class AirwayLandmarks(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Airway Landmarks" # TODO make this more human readable by adding spaces
    self.parent.categories = ["Airway 4D Tools"]
    self.parent.dependencies = []
    self.parent.contributors = ["Mike Bindschadler (Seattle Children's Hospital)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This module helps users mark landmarks for evaluating airways in 3D or 4D CT series.
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
This file was originally developed by Mike Bindschadler, Seattle Children's Hospital.
""" # replace with organization, grant and thanks.

#
# AirwayLandmarksWidget
#

class AirwayLandmarksWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    print('Running setup!')

    # Create or get the parameter node to store user choices
    self.parameterNode = AirwayLandmarksLogic().getParameterNode()
    pn = self.parameterNode

    fhLandmarkStringsList = ['Left ear FH', 'Right ear FH', 'Left orbit FH']
    FHLandmarksNodeName = 'FH_Landmarks'
    tempLandmarkNodeName = 'TempLandmark'
    landmarksNodeName = 'Airway_Landmarks'

    # Initialize parameter node if there are nodes with these names already
    try:
      landmarksNode = slicer.util.getNode(landmarksNodeName)
      pn.SetParameter('AirwayLandmarksNode_ID', landmarksNode.GetID())
      self.landmarksNode = landmarksNode
    except slicer.util.MRMLNodeNotFoundException:
      pn.SetParameter('AirwayLandmarksNode_ID','')
      self.landmarksNode = None
    try:
      FHLandmarksNode = slicer.util.getNode(FHLandmarksNodeName)
      pn.SetParameter('FHLandmarksNode_ID', FHLandmarksNode.GetID())
      self.FHLandmarksNode = FHLandmarksNode
    except slicer.util.MRMLNodeNotFoundException:
      pn.SetParameter('FHLandmarksNode_ID','')
      self.FHLandmarksNode = None

    # The temp node should always be cleared and recreated
    try:
      slicer.mrmlScene.RemoveNode(slicer.util.getNode(tempLandmarkNodeName))
    except slicer.util.MRMLNodeNotFoundException:
      print('No old tempLandmarks node to remove')
      pass
    self.tempLandmarkNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode',tempLandmarkNodeName)
    pn.SetParameter('TempLandmarkNode_ID', self.tempLandmarkNode.GetID())

    # TODO: convert to pandas data frame and include tooltips for each of these
    landmarkMidSagDict = {
      'Vomer (posterior aspect)': False,
      'Anterior Nasal Spine': False,
      'C4 (anterior inferior aspect)': True,
      'C2 (anterior inferior aspect)': True,
      'Vallecula (inferior aspect)': True,
      'Tongue (superior aspect)': True,
      'Tongue (anterior aspect)': True,
      'C3 (anterior aspect)': True,
      'Hyoid (central point)': True,
      'Pogonion': True,
      'Nasion': True,
      'Basion': True,
      'Left gonion': False,
      'Left condylion': False,
      'Right gonion': False,
      'Right condylion': False,
      'Adenoids': False,
      'Epigottis (superior tip)': False,
      'Base of tongue': False,
      'Glottis (anterior commissure)': False      
    }
    landmarkStrings = list(landmarkMidSagDict.keys())
    midSagBools = list(landmarkMidSagDict.values())
    # TODO Make it work so that if there is an existing node with the right name, you load it instead of removing it. 
    # Maybe Add any landmarks that are listed above and missing from the current one (but don't delete extras?)
    # TODO add ability to sync from node
    # TODO add ability to switch nodes or create new... (node selector with New option)

    # Bind a keyboard shortcut of pressing 'h' to toggle display of already placed landmarks (non-FH)
    #shortcutKeys  These are connected later, in the enter() function
    self.shortcutH = qt.QShortcut(slicer.util.mainWindow())
    self.shortcutH.setKey(qt.QKeySequence('h'))
    self.shortcutM = qt.QShortcut(slicer.util.mainWindow())
    self.shortcutM.setKey(qt.QKeySequence('m'))
    #self.connectKeyboardShortcuts()

    # Instantiate and connect widgets ...

    
    # FH point selection
    # Idea is to have a table widget which will indicate and track the landmarks to connect
    # Start with FH points, which should be in a separate table

    # FH Points
    reorientCollapsibleButton = ctk.ctkCollapsibleButton()
    reorientCollapsibleButton.text = 'Reorientation'
    self.layout.addWidget(reorientCollapsibleButton)
    self.reorientFormLayout = qt.QFormLayout(reorientCollapsibleButton)

    # CT Volume selector
    self.CTVolumeSelector = slicer.qMRMLNodeComboBox()
    self.CTVolumeSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
    self.CTVolumeSelector.selectNodeUponCreation = True
    self.CTVolumeSelector.addEnabled = False
    self.CTVolumeSelector.removeEnabled = False
    self.CTVolumeSelector.noneEnabled = False
    self.CTVolumeSelector.showHidden = False
    self.CTVolumeSelector.showChildNodeTypes = False
    self.CTVolumeSelector.setMRMLScene( slicer.mrmlScene )
    self.CTVolumeSelector.setToolTip('Choose the CT volume you will annotate')
    self.reorientFormLayout.addRow('CT Volume',self.CTVolumeSelector)

    # FH node selector
    self.FHLandmarksNodeSelector = slicer.qMRMLNodeComboBox()
    self.FHLandmarksNodeSelector.nodeTypes = ['vtkMRMLMarkupsFiducialNode']
    self.FHLandmarksNodeSelector.noneEnabled = True
    self.FHLandmarksNodeSelector.addEnabled = True
    self.FHLandmarksNodeSelector.selectNodeUponCreation = False
    self.FHLandmarksNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.FHLandmarksNodeSelector.setToolTip('Choose Fiducial node to hold Frankfurt Horizontal defining points')
    self.reorientFormLayout.addRow('FH Points', self.FHLandmarksNodeSelector)

    # Build the FH table 
    self.fhTable = self.buildLandmarkTable(fhLandmarkStringsList)
    AirwayLandmarksLogic().fitTableSize(self.fhTable)
    self.reorientFormLayout.addRow(self.fhTable)
    # add the reorient button
    self.reorientButton = qt.QPushButton('Reorient')
    self.reorientFormLayout.addRow(self.reorientButton)
    
    if self.FHLandmarksNode is None:
      # There was no matching node at start up, create it
      self.FHLandmarksNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode', FHLandmarksNodeName)
    else:
      # Already existing, fill table from it
      AirwayLandmarksLogic().updateLandmarkTableFromNode(self.fhTable, self.FHLandmarksNode)
    self.FHLandmarksNodeSelector.setCurrentNode(self.FHLandmarksNode) # Initialize selector

    # 
    landmarksCollapsibleButton = ctk.ctkCollapsibleButton()
    landmarksCollapsibleButton.text = 'Landmarks'
    self.layout.addWidget(landmarksCollapsibleButton)
    self.landmarksFormLayout = qt.QFormLayout(landmarksCollapsibleButton)

    # Landmarks Node Selector
    self.landmarksNodeSelector = slicer.qMRMLNodeComboBox()
    self.landmarksNodeSelector.nodeTypes = ['vtkMRMLMarkupsFiducialNode']
    self.landmarksNodeSelector.addEnabled = True
    self.landmarksNodeSelector.selectNodeUponCreation = False
    self.landmarksNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.landmarksNodeSelector.setToolTip('Choose Fiducial node to hold airway landmark point locations')
    self.landmarksFormLayout.addRow('Landmark Points', self.landmarksNodeSelector)

    # Main Landmark table
    self.landmarksTable = self.buildLandmarkTable(landmarkStrings,mid_sag_bool_dict=landmarkMidSagDict, include_sag_col=True)
    self.landmarksFormLayout.addRow(self.landmarksTable)
    AirwayLandmarksLogic().fitTableSize(self.landmarksTable)
    if self.landmarksNode is None:
      self.landmarksNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsFiducialNode', landmarksNodeName)
    else:
      AirwayLandmarksLogic().updateLandmarkTableFromNode(self.landmarksTable, self.landmarksNode)
    self.landmarksNodeSelector.setCurrentNode(self.landmarksNode)

    # Calculate
    calculateCollapsibleButton = ctk.ctkCollapsibleButton()
    calculateCollapsibleButton.text = 'Calculate'
    self.layout.addWidget(calculateCollapsibleButton)
    self.calculateFormLayout = qt.QFormLayout(calculateCollapsibleButton)
    self.calculateLandmarkMeasuresButton = qt.QPushButton('Calculate Landmark Measures')
    self.calculateFormLayout.addRow(self.calculateLandmarkMeasuresButton)
    self.measuresText = qt.QTextEdit()
    self.calculateFormLayout.addRow(self.measuresText)

    # Export
    exportCollapsibleButton = ctk.ctkCollapsibleButton()
    exportCollapsibleButton.text = 'Export'
    self.layout.addWidget(exportCollapsibleButton)
    self.exportFormLayout = qt.QFormLayout(exportCollapsibleButton)
    self.createCSVButton = qt.QPushButton('Create CSV')
    self.exportFormLayout.addRow(self.createCSVButton)
    self.addToCSVButton = qt.QPushButton('Add to CSV')
    self.exportFormLayout.addRow(self.addToCSVButton)
    

    # Connect callbacks
    self.CTVolumeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onCTVolumeSelectorChange)
    self.fhTable.connect('cellClicked(int,int)',lambda row,col: self.onTableCellClicked(row,col,self.fhTable))
    self.tempLandmarkNode.AddObserver(self.tempLandmarkNode.PointPositionDefinedEvent, self.onLandmarkClick)
    self.reorientButton.connect('clicked(bool)',self.onReorientButtonClick)
    self.landmarksTable.connect('cellClicked(int,int)',lambda row,col: self.onTableCellClicked(row,col,self.landmarksTable))
    self.calculateLandmarkMeasuresButton.connect('clicked(bool)', self.onCalculateButtonClick)
    self.FHLandmarksNodeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onFHLandmarksNodeSelectorChange)
    self.landmarksNodeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onLandmarksNodeSelectorChange)
    self.createCSVButton.connect('clicked(bool)', self.onCreateCSVButtonClick)
    self.addToCSVButton.connect('clicked(bool)', self.onAddToCSVButtonClick)


    '''
    # Set the temporary node as the current Markups node
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode") # set type of node
    selectionNode.SetActivePlaceNodeID(self.tempLandmarkNode.GetID()) # set temp node as the active one for placement
    # activate point placement mode (do we want to do this on setup here?, I think so)
    interactionNode = slicer.app.applicationLogic().GetInteractionNode()
    interactionNode.SetCurrentInteractionMode(interactionNode.Place) # activate placement mode
    # Set the first cell as active and call as if clicked on
    self.fhTable.setCurrentItem(self.fhTable.item(0,0))
    self.fhTable.setFocus() # not sure if this is needed
    '''
    # OR we could just
    self.onTableCellClicked(0,0,self.fhTable)
    self.fhTable.setCurrentItem(self.fhTable.item(0,0))
    self.fhTable.setFocus() # not sure if this is needed

    self.onCTVolumeSelectorChange() # to initialize parameter node


  def enter(self):
    '''Runs whenever the module is switched to, but apparently not on reload'''
    #print('Entered!')
    self.connectKeyboardShortcuts()

  def exit(self):
    '''Runs whenver the module is switched away from'''
    #print('Exited!')
    self.disconnectKeyboardShortcuts()
  
  def cleanup(self):
    '''Runs whenever the module is closed or about to be reloaded'''
    #print('Running cleanup')  
    self.disconnectKeyboardShortcuts()

  def onCTVolumeSelectorChange(self):
    # update parameter node 'vol_id'
    new_vol_node = self.CTVolumeSelector.currentNode()
    if new_vol_node is None:
      self.parameterNode.SetParameter('vol_id','')
    else:
      self.parameterNode.SetParameter('vol_id', new_vol_node.GetID())
    # TODO also change this volume to the displayed background layer volume? Probably a good idea

  def onFHLandmarksNodeSelectorChange(self):
    # update parameter node and update table
    new_fh_node = self.FHLandmarksNodeSelector.currentNode()
    if new_fh_node is None:
      self.parameterNode.SetParameter('FHLandmarksNode_ID', '')
    else:
      self.parameterNode.SetParameter('FHLandmarksNode_ID', new_fh_node.GetID())
    self.FHLandmarksNode = new_fh_node
    AirwayLandmarksLogic().updateLandmarkTableFromNode(self.fhTable, self.FHLandmarksNode)

  def onLandmarksNodeSelectorChange(self):
    # update parameter node and update table
    new_landmarks_node = self.landmarksNodeSelector.currentNode()
    if new_landmarks_node is None:
      self.parameterNode.SetParameter('AirwayLandmarksNode_ID', '')
    else:
      self.parameterNode.SetParameter('AirwayLandmarksNode_ID', new_landmarks_node.GetID())
    self.landmarksNode = new_landmarks_node
    AirwayLandmarksLogic().updateLandmarkTableFromNode(self.landmarksTable, self.landmarksNode)

  def connectKeyboardShortcuts(self):
    '''Connect 'h' to show/hide landmarks and 'm' to toggle fiducial placement mode'''
    #print('Connecting')
    self.shortcutH.connect('activated()', self.onHKeyPressed)
    self.shortcutM.connect('activated()', self.onMKeyPressed)

  def disconnectKeyboardShortcuts(self):
    #print('Disconnecting')
    self.shortcutH.activated.disconnect()
    self.shortcutM.activated.disconnect()

  def onHKeyPressed(self):
    #print('H key pressed!')
    newState = AirwayLandmarksLogic().toggleLandmarkVisibility(self.landmarksNode)
    # Set the FH landmarks to same visibility as main landmarks
    self.FHLandmarksNode.GetDisplayNode().SetVisibility(newState)
  
  def onMKeyPressed(self):
    #print('M key pressed')
    AirwayLandmarksLogic().togglePlacementMode()

  def onCalculateButtonClick(self):
    # Triggers calculation of landmark measures given current landmark positions
    report_str = AirwayLandmarksLogic().calculate_measures(self.landmarksNode)
    self.measuresText.setText(report_str)
    self.parameterNode.SetParameter('report_str', report_str)

  def onCreateCSVButtonClick(self):
    # Button clicked to create new csv file
    csvPathAndName = qt.QFileDialog().getSaveFileName() 
    if csvPathAndName != '':
      report_str = self.parameterNode.GetParameter('report_str')
      vol_id = self.parameterNode.GetParameter('vol_id')
      try:
        vol_name = slicer.util.getNode(vol_id).GetName()
      except slicer.util.MRMLNodeNotFoundException:
        vol_name = 'NoneSelected'
      AirwayLandmarksLogic().create_csv(csvPathAndName, report_str, vol_name)

  def onAddToCSVButtonClick(self):
    # Button clicked to add line to existing csv file
    csvPathAndName = qt.QFileDialog().getOpenFileName()
    if csvPathAndName != '':
      report_str = self.parameterNode.GetParameter('report_str')
      vol_id = self.parameterNode.GetParameter('vol_id')
      try:
        vol_name = slicer.util.getNode(vol_id).GetName()
      except slicer.util.MRMLNodeNotFoundException:
        vol_name = 'NoneSelected'
      AirwayLandmarksLogic().add_to_csv(csvPathAndName, report_str, vol_name)

  def buildLandmarkTable(self,landmarkStringsList, mid_sag_bool_dict={}, include_sag_col=False):
    table = qt.QTableWidget()
    rowCount = len(landmarkStringsList)
    table.setRowCount(rowCount)
    if include_sag_col:
      colHeaders = ['Landmark','Mid-Sag','R','A','S','Reset']
    else:
      colHeaders = ['Landmark','R','A','S','Reset']
    colCount = len(colHeaders)
    table.setColumnCount(colCount)
    table.setHorizontalHeaderLabels(colHeaders)
    for row in range(rowCount):
      landmarkName = landmarkStringsList[row]
      for col in range(colCount):
        cell = qt.QTableWidgetItem()
        table.setItem(row,col,cell)
        if col==0:
          cell.setText(landmarkName)
          cell.setFlags(qt.Qt.ItemIsSelectable + qt.Qt.ItemIsEnabled) # enabled and selectable, but not editable (41 would allow drop onto)
        elif include_sag_col and col==1:
          # sag col
          forceMidSag = mid_sag_bool_dict[landmarkName]
          if forceMidSag:
            cell.setCheckState(qt.Qt.Checked)
          else:
            cell.setCheckState(qt.Qt.Unchecked)
          cell.setFlags(qt.Qt.ItemIsEnabled) # could also do qt.Qt.ItemIsUserCheckable + qt.Qt.ItemIsEnable
        elif col==colCount-1:
          # Last column is reset column
          cell.setText('[X]')
          cell.setFlags(qt.Qt.ItemIsSelectable + qt.Qt.ItemIsEnabled)
        else:
          # Other columns (RAS)
          cell.setFlags(qt.Qt.ItemIsSelectable + qt.Qt.ItemIsEnabled)#qt.Qt.NoItemFlags) 
    return table


    
  def onTableCellClicked(self,row,col,table):
    landmarkName = table.item(row,0).text()
    self.tempLandmarkNode.SetMarkupLabelFormat(landmarkName)
    if table == self.fhTable:
      self.currentRealLandmarksNode = self.FHLandmarksNode
    else:
      self.currentRealLandmarksNode = self.landmarksNode
    # Activate point placement mode and make the temp landmark node the current one
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode") # set type of node
    selectionNode.SetActivePlaceNodeID(self.tempLandmarkNode.GetID()) # set temp node as the active one for placement
    interactionNode = slicer.app.applicationLogic().GetInteractionNode()
    interactionNode.SetCurrentInteractionMode(interactionNode.Place) # activate placement mode
    interactionNode.SwitchToPersistentPlaceMode() # make it persistent
    # If reset clicked, do the reset
    if col==(table.columnCount-1):
      # Remove existing coordinates from real landmark node
      for cpIdx in range(self.currentRealLandmarksNode.GetNumberOfControlPoints()):
        label = self.currentRealLandmarksNode.GetNthControlPointLabel(cpIdx)
        if label==landmarkName:
          print('Resetting '+landmarkName)
          self.currentRealLandmarksNode.RemoveNthControlPoint(cpIdx)
          # Clear out table coordinates
          AirwayLandmarksLogic().updateLandmarkTableEntry(table, landmarkName, landmarkPosition=None)


    


  def onLandmarkClick(self,caller,event):
    # event is NoEvent
    # Caller is the temp landmark node, I believe
    # Clicking point placement on a view should:
    #  1. transfer the clicked point location to the real landmarks node
    #  2. update the table with RAS location (how do I know if it is FH table or other table?)
    #  2. delete it from the temporary one
    #  3. select the next unfilled landmark location on the table 
    #  4. rename temp landmark node default name to be this next landmark (or deselect point placement mode and make default name 'You're finished!')
    tempNode = caller # same as self.tempLandmarkNode
    # Get the temp control point position
    pos = [0]*3
    tempNode.GetNthControlPointPositionWorld(0,pos)
    realNode = self.currentRealLandmarksNode
    
    # Get the landmark name
    landmarkName = tempNode.GetNthControlPointLabel(0)
    print('Landmark name: '+landmarkName)
    # Check if the real landmark node already has a control point with this name
    replaceCpIdx = None
    for cpIdx in range(realNode.GetNumberOfControlPoints()):
      cpLabel = realNode.GetNthControlPointLabel(cpIdx)
      if cpLabel==landmarkName:
        replaceCpIdx = cpIdx # replace this one
    if replaceCpIdx is not None:
      realNode.SetNthControlPointPositionWorld(replaceCpIdx, *pos)
      cpIdx = replaceCpIdx
    else:
      # add as new control point
      cpIdx = realNode.AddControlPointWorld( vtk.vtkVector3d(*pos) )
      realNode.SetNthControlPointLabel(cpIdx, landmarkName)
    # Either way, lock the point so you don't accidentally move it with the mouse
    realNode.SetNthControlPointLocked(cpIdx, True)
    # Update the landmark table with the position
    success = AirwayLandmarksLogic().updateLandmarkTableEntry(self.fhTable, landmarkName, pos)
    if not success:
      # Try the other landmark table
      success = AirwayLandmarksLogic().updateLandmarkTableEntry(self.landmarksTable, landmarkName, pos)
      if not success:
        print('Table updating failed on both FH and full Landmark table')
      pass
    # Clear out temp control point
    tempNode.RemoveAllControlPoints()
    # Select the next unmarked row
    if AirwayLandmarksLogic().selectNextUnfilledRow(self.fhTable) is None:
      AirwayLandmarksLogic().selectNextUnfilledRow(self.landmarksTable)
    

    #print('Landmark Name Later: '+landmarkName)
    #print(caller)
    #print(event)

  def onReorientButtonClick(self):
    # User clicked FH reorient button, do the reorientation
    # Tricky part is handling what should happen with all existing lanmarks
    # I think what should happen is a hardened transform of them into new FH image space
    # This will keep them synchronized with the image even if FH reorientation is done repeatedly
    # TODO: In terms of the FH transform, we want that to represent the transform from the ORIGINAL orientation
    # (from DICOM or from initial load), so that needs to be made cumulative somehow, not just reflecting
    # the most recent FH reorientation
    print('Reorienting...')
    points_FH_Transform = make_FH_transform(self.FHLandmarksNode)
    # Apply transform to the CT volume
    volNode = self.CTVolumeSelector.currentNode()
    if volNode is None:
      raise Exception('No CT volume selected')

    try:
      volTransform = slicer.util.getNode('volume_FH_Transform')
    except slicer.util.MRMLNodeNotFoundException:
      volTransform = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode','volume_FH_Transform')

    if volNode.GetTransformNodeID() is None:
      # No existing transform, just use the new one
      matrix = vtk.vtkMatrix4x4()
      points_FH_Transform.GetMatrixTransformToParent(matrix)
      volTransform.SetMatrixTransformToParent(matrix)
    else:
      #need to compose old and new transforms
      oldVolTransform = slicer.util.getNode(volNode.GetTransformNodeID())
      oldTransformMatrix = vtk.vtkMatrix4x4()
      oldVolTransform.GetMatrixTransformToParent(oldTransformMatrix)
      newTransformMatrix = vtk.vtkMatrix4x4()
      points_FH_Transform.GetMatrixTransformToParent(newTransformMatrix)
      combinedTransformMatrix = vtk.vtkMatrix4x4()
      vtk.vtkMatrix4x4().Multiply4x4(oldTransformMatrix, newTransformMatrix, combinedTransformMatrix)
      volTransform.SetMatrixTransformToParent(combinedTransformMatrix)
    volNode.SetAndObserveTransformNodeID(volTransform.GetID())

    # Apply points transform to all existing landmarks so that they move with the volume
    self.FHLandmarksNode.SetAndObserveTransformNodeID(points_FH_Transform.GetID())
    self.landmarksNode.SetAndObserveTransformNodeID(points_FH_Transform.GetID())
    # Harden to make change permanent
    slicer.vtkSlicerTransformLogic().hardenTransform(self.FHLandmarksNode)
    slicer.vtkSlicerTransformLogic().hardenTransform(self.landmarksNode)
    # Update the tables 
    for cpIdx in range(self.FHLandmarksNode.GetNumberOfControlPoints()):
      landmarkName = self.FHLandmarksNode.GetNthControlPointLabel(cpIdx)
      newPos = [0]*3
      self.FHLandmarksNode.GetNthControlPointPositionWorld(cpIdx,newPos)
      AirwayLandmarksLogic().updateLandmarkTableEntry(self.fhTable, landmarkName, newPos)
    for cpIdx in range(self.landmarksNode.GetNumberOfControlPoints()):
      landmarkName = self.landmarksNode.GetNthControlPointLabel(cpIdx)
      newPos = [0]*3
      self.landmarksNode.GetNthControlPointPositionWorld(cpIdx,newPos)
      AirwayLandmarksLogic().updateLandmarkTableEntry(self.landmarksTable, landmarkName, newPos)

 
  '''
  OK, what do I need to set up?  
  * Temporary Fidicual Node
  * Real Fiducial Node
  * Clicking on a row should:
    * If that point is not yet defined, change the temporary node default name to that name, and activate point placement
    * If that point is already defined?  Not sure yet.  Auto-replace?  That would be why we need a temporary name.  If Mid-Sag point, jump to mid sag plane!
  * Clicking on reset for a row should remove existing coordinates, activate point placement
  * Clicking point placement on a view should:
    * transfer that clicked point location to the real fiducial node, delete it from the temp one, select the next unfilled landmark location on the table, rename temp default name to new row
    * if there are no more empty landmark locations, unselect table cell (not sure how), and unselect placement node
  * 
  '''

#
# AirwayLandmarksLogic
#

class AirwayLandmarksLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def calculate_measures(self, landmarks_node):
    '''Calculate all possible airway measures.  If a needed landmark point is missing, just
    report Not Available in the result'''
    def get_landmark(landmark_name):
      # find landmark with given name in landmarks node, or return None if not found
      N = landmarks_node.GetNumberOfControlPoints()
      found = False
      for idx in range(N):
        cur_name = landmarks_node.GetNthControlPointLabel(idx)
        if cur_name==landmark_name:
          found = True
          pos = [0]*3
          landmarks_node.GetNthControlPointPositionWorld(idx,pos)
      if found:
        return pos
      else: 
        logging.info('Landmark "%s" not found!!' % (landmark_name))
        return None
    tongue_superior = get_landmark('Tongue (superior aspect)')
    tongue_anterior = get_landmark('Tongue (anterior aspect)')
    vallecula = get_landmark('Vallecula (inferior aspect)')
    ans = get_landmark('Anterior Nasal Spine')
    hyoid = get_landmark('Hyoid (central point)')
    c2 = get_landmark('C2 (anterior inferior aspect)')
    c3 = get_landmark('C3 (anterior aspect)')
    pog = get_landmark('Pogonion')
    nasion = get_landmark('Nasion')
    basion = get_landmark('Basion')
    left_condylion = get_landmark('Left condylion')
    left_gonion = get_landmark('Left gonion')
    right_condylion = get_landmark('Right condylion')
    right_gonion = get_landmark('Right gonion')

    R=0
    A=1
    S=2

    report_str = ''
    def make_report_line(measure_name, measure_value, units, number_format="%0.1f"):
      if measure_value is None:
        str = '%s: NotAvailable\n' % measure_name
      else:
        str = '%s: %s %s\n' % (measure_name, number_format % measure_value, units)
      return str

    # Tongue height
    tongue_height = None
    if all_not_none(tongue_superior, vallecula):
      tongue_height = tongue_superior[S] - vallecula[S]
    report_str += make_report_line("Tongue height", tongue_height, "mm")
    # Tongue anterior position
    tongue_anterior_pos = None
    if all_not_none(tongue_anterior, ans):
      tongue_anterior_pos = ans[A] - tongue_anterior[A] 
    report_str += make_report_line("Tongue anterior position", tongue_anterior_pos, "mm", number_format="%+0.1f")
    # Tongue superior position
    tongue_superior_pos = None
    if all_not_none(tongue_superior, ans):
      tongue_superior_pos = ans[S] - tongue_superior[S]
    report_str += make_report_line("Tongue superior position (relative to anterior nasal spine)", tongue_superior_pos, "mm", number_format="%+0.1f")
    # Hyoid posterior distance
    hyoid_posterior_distance = None
    if all_not_none(hyoid, c2, c3):
      # Need to find shortest distance from line connecting c2 and c3 to hyoid center
      # Can be reformulated as subtracting the projection of h-c2 onto c2-c3 from h-c2
      line_vector = np.subtract(c3,c2) # vector pointing along line
      h_to_c2 = np.subtract(c2, hyoid)
      proj = project(h_to_c2, line_vector) # projection of h_to_c2 onto line connecting c2 and c3
      perp = h_to_c2 - proj # component perpedicular to line
      hyoid_posterior_distance = np.linalg.norm(perp) 
    report_str += make_report_line("Hyoid posterior distance (relative to C2-C3)", hyoid_posterior_distance, 'mm')
    # Hyoid anterior distance
    hyoid_anterior_distance = None
    if all_not_none(hyoid, pog):
      hyoid_anterior_distance = distance_sag(hyoid, pog) # sagittal plane distance
    report_str += make_report_line("Hyoid anterior distance (relative to pogonion)", hyoid_anterior_distance, 'mm')
    # Hyoid craniocaudal position
    hyoid_craniocaudal_position = None
    if all_not_none(hyoid, ans):
      hyoid_craniocaudal_position = hyoid[S] -ans[S]
    report_str += make_report_line("Hyoid craniocaudal position (relative to anterior nasal spine)", hyoid_craniocaudal_position, 'mm', number_format="%+0.1f")
    # Nasion to Basion
    nasion_to_basion_distance = None
    if all_not_none(nasion, basion):
      nasion_to_basion_distance = distance_3D(nasion, basion)
    report_str += make_report_line("Nasion to Basion distance", nasion_to_basion_distance, 'mm')
    # Left Mandibular Ramus Height
    left_mandib_ramus_height = None
    if all_not_none(left_condylion, left_gonion):
      left_mandib_ramus_height = distance_3D(left_condylion, left_gonion)
    report_str += make_report_line('Left mandibular ramus height', left_mandib_ramus_height, 'mm')
    # Right Mandibular Ramus Height
    right_mandib_ramus_height = None
    if all_not_none(right_condylion, right_gonion):
      right_mandib_ramus_height = distance_3D(right_condylion, right_gonion)
    report_str += make_report_line('Right mandibular ramus height', right_mandib_ramus_height, 'mm')
    # Inferior Pogonial Angle
    inferior_pognial_angle = None
    if all_not_none(left_gonion, right_gonion, pog):
      inferior_pognial_angle = angle(np.subtract(left_gonion, pog), np.subtract(right_gonion, pog))
    report_str += make_report_line('Inferior pogonial angle', inferior_pognial_angle, 'degrees')
    # Bigonial Distance
    bigonial_distance = None
    if all_not_none(left_gonion, right_gonion):
      bigonial_distance = distance_3D(left_gonion, right_gonion)
    report_str += make_report_line('Bigonial distance', bigonial_distance, 'mm')
    # Left Mandibular Body Length
    left_mandib_body_len = None
    if all_not_none(left_gonion, pog):
      left_mandib_body_len = distance_3D(left_gonion, pog)
    report_str += make_report_line('Left mandibular body length', left_mandib_body_len, 'mm')
    # Right Mandibular Body Length
    right_mandib_body_len = None
    if all_not_none(right_gonion, pog):
      right_mandib_body_len = distance_3D(right_gonion, pog)
    report_str += make_report_line('Right mandibular body length', right_mandib_body_len, 'mm')
    # Left Mandibular Total Length
    left_mandib_total_len = None
    if all_not_none(left_condylion, pog):
      left_mandib_total_len = distance_3D(left_condylion, pog)
    report_str += make_report_line('Left mandibular total length (condylion to pogonion line)', left_mandib_total_len, 'mm')
    # Right Mandibular Total Length
    right_mandib_total_len = None
    if all_not_none(right_condylion, pog):
      right_mandib_total_len = distance_3D(right_condylion, pog)
    report_str += make_report_line('Right mandibular total length (condylion to pogonion line)', right_mandib_total_len, 'mm')
    # Left Gonial Angle Substitute
    left_gonial_angle_substitute = None
    if all_not_none(left_condylion, left_gonion, pog):
      left_gonial_angle_substitute = angle(np.subtract(left_gonion, left_condylion), np.subtract(left_gonion, pog))
    report_str += make_report_line("Left gonial angle substitute (condyl-gon-pog)", left_gonial_angle_substitute, 'degrees')
    # Right Gongial Angle Substitute
    right_gonial_angle_substitute = None
    if all_not_none(right_condylion, right_gonion, pog):
      right_gonial_angle_substitute = angle(np.subtract(right_gonion, right_condylion), np.subtract(right_gonion, pog))
    report_str += make_report_line("Right gonial angle substitute (condyl-gon-pog)", right_gonial_angle_substitute, 'degrees')
    

    logging.info(report_str)

    return report_str


  def create_csv(self, filename, report_str, volume_name):
    # create csv of airway measure values and fill first row of data
    # Ensure extension is .csv
    if len(filename)<4 or filename[-4:]!='.csv':
      filename += '.csv'
    import csv
    colNames = [rl.split(': ')[0] for rl in report_str.splitlines()]
    colNames.append('Volume Name')
    colVals = [rl.split(': ')[1] for rl in report_str.splitlines()]
    units = [val.split(' ')[1] for val in colVals]
    vals = [val.split(' ')[0] for val in colVals]
    vals.append(volume_name)
    with open(filename, mode='w', newline='') as f:
      writer = csv.writer(f)
      writer.writerow(colNames)
      writer.writerow(units)
      writer.writerow(vals)

  def add_to_csv(self, filename, report_str, volume_name):
    # to add one line of values to existing csv file
    # Ensure filename exists
    import os.path
    if not os.path.exists(filename):
      slicer.util.warningDisplay('File "%s" does not exist!'%(filename))
      return
    import csv
    colVals = [rl.split(': ')[1] for rl in report_str.splitlines()]
    v = [val.split(' ')[0] for val in colVals]
    v.append(volume_name)
    with open(filename, mode='a', newline='') as f:
      writer = csv.writer(f)
      writer.writerow(v)
  

  def updateLandmarkTableEntry(self, table, landmarkName, landmarkPosition):
    """ Checks through given table for a row that starts with landmarkName.
    If found, the supplied position is filled in, and function returns True.
    If not found, the function returns False
    """
    foundLandmarkName=False
    numberFormat = '%0.1f'
    Scol = table.columnCount-2 # 2nd from last
    Acol = table.columnCount-3 # 3rd from last
    Rcol = table.columnCount-4 # 4th from last
    for rowIdx in range(table.rowCount):
      rowLandmarkName = table.item(rowIdx,0).text()
      #print('%s==%s'%(landmarkName,rowLandmarkName))
      if rowLandmarkName==landmarkName:
        foundLandmarkName = True
        if landmarkPosition is None:
          # Reset position text to empty strings
          table.item(rowIdx,Scol).setText('')
          table.item(rowIdx,Acol).setText('')
          table.item(rowIdx,Rcol).setText('')
        else:
          # Match! Fill in position
          R,A,S = landmarkPosition  
          table.item(rowIdx,Scol).setText(numberFormat % S)
          table.item(rowIdx,Acol).setText(numberFormat % A)
          table.item(rowIdx,Rcol).setText(numberFormat % R)
    self.fitTableSize(table)
    return foundLandmarkName

  def updateLandmarkTableFromNode(self, table, landmarks_node):
    # Loop over table entries and fill from landmarks node.  
    # Note that this will omit any extra points which are present in the landmarks_node but not present in the table
    node_landmark_labels = []
    if landmarks_node is not None:
      for cpIdx in range(landmarks_node.GetNumberOfControlPoints()):
        node_landmark_labels.append(landmarks_node.GetNthControlPointLabel(cpIdx))
    for rowIdx in range(table.rowCount):
      rowLandmarkName = table.item(rowIdx,0).text()
      try:
        idx = node_landmark_labels.index(rowLandmarkName)
        pos = [0]*3
        landmarks_node.GetNthControlPointPositionWorld(idx, pos)
        self.updateLandmarkTableEntry(table, rowLandmarkName, pos)
      except AttributeError:
        # landmarks_node must be None, clear table row
        pos = None
      except ValueError:
        # rowLandmarkName not found in list of node landmark labels
        # Clear the table row...
        pos = None
      self.updateLandmarkTableEntry(table, rowLandmarkName, landmarkPosition=pos)
   
    
    
  def selectNextUnfilledRow(self,table):
    # Find the currently selected row
    if len(table.selectedIndexes())==0:
      row=0 # default to 0 if no selected cell
    else:
      row = table.selectedIndexes()[0].row() # start from currently selected cell
    unfilledRowIdx = None
    for rowIdx in range(row,table.rowCount):
      if not self.rowIsFilled(table,rowIdx):
        unfilledRowIdx = rowIdx
        break
    # If not found yet, start again at the top of the table
    if unfilledRowIdx is None:
      for rowIdx in range(row):
        if not self.rowIsFilled(table,rowIdx):
          unfilledRowIdx = rowIdx
          break
    # Now we've been through the whole table
    if unfilledRowIdx is None:
      # No empty rows!
      # TODO: Should something else happen here?
      table.clearSelection() # unselect all
      # I want to change 
      interactionNode = slicer.app.applicationLogic().GetInteractionNode()
      interactionNode.SetCurrentInteractionMode(interactionNode.ViewTransform) # activate regular mode (arrow pointer cursor)
    else:
      # Unfilled row identified
      # Select this row
      table.setCurrentItem(table.item(unfilledRowIdx,0))
      # Trigger callback as if clicked
      table.cellClicked(unfilledRowIdx,0)
    return unfilledRowIdx # None if none found

    
  def rowIsFilled(self,table,rowIdx):
    # A row is filled if the 3rd column has a coordinate in it (either R or A
    # depending on whether sag coll is there)
    text = table.item(rowIdx,2).text()
    if is_number(text):
      return True
    else:
      return False


  def fitTableSize(self,table):
    # change the table size to have no scrollbars and be minimal size
    # based on https://stackoverflow.com/questions/8766633/how-to-determine-the-correct-size-of-a-qtablewidget
    growFlag = 1 #https://doc.qt.io/qt-5/qsizepolicy.html#PolicyFlag-enum
    table.setSizePolicy(growFlag,growFlag)
    table.setVerticalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
    table.setHorizontalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
    table.resizeColumnsToContents()
    width = table.horizontalHeader().length()+table.verticalHeader().width
    height = table.verticalHeader().length()+table.horizontalHeader().height
    table.setFixedSize(width,height)  


  def toggleLandmarkVisibility(self,markupsNode):
    # TODO: consider changing this so it hides the labels, but not the points...
    oldState = markupsNode.GetDisplayNode().GetVisibility()
    newState = not oldState
    markupsNode.GetDisplayNode().SetVisibility(newState)
    return newState

  def togglePlacementMode(self):
    # If interaction mode is not "Place", switch to place mode; if it is "Place",
    # then switch to regular mode (which is called ViewTransform)
    interactionNode = slicer.app.applicationLogic().GetInteractionNode()
    if interactionNode.GetCurrentInteractionMode()== interactionNode.Place:
      # switch to regular arrow curson mode
      interactionNode.SetCurrentInteractionMode(interactionNode.ViewTransform)
    else:
      # switch to placement mode
      interactionNode.SetCurrentInteractionMode(interactionNode.Place)



  
class AirwayLandmarksTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_SEEGR1()

  def test_SEEGR1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import SampleData
    SampleData.downloadFromURL(
      nodeNames='FA',
      fileNames='FA.nrrd',
      uris='http://slicer.kitware.com/midas3/download?items=5767')
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = SEEGRLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')


#
# Helper functions
#

def is_number(text):
  try:
    float(text)
    return True
  except ValueError:
    return False

def all_not_none(*args):
  # Returns True if all inputs are not None, otherwise returns False
  for arg in args:
    if arg is None:
      return False # at least this argument is None
  return True #all arguments were not None

def project(u, v):
  # Returns the projection of u onto v
  proj = np.dot(u,v) / np.linalg.norm(v)**2 * np.array(v) 
  return proj

def distance_sag(p1, p2):
    # Find distance between point 1 and 2 ignoring the R coordinate, i.e. projecting
    # the two into a common sagittal plane before finding the distance between them.
    p1 = np.array(p1)
    p2 = np.array(p2)
    dist_sag = np.sqrt((p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)
    return dist_sag

def distance_3D(p1,p2):
  # Find 3D distance between points 1 and 2
  dist = np.linalg.norm(np.subtract(p2,p1))
  return dist

def angle(v1,v2):
  # Find angle between the two given vectors in degrees, 0 to 180
  ang_deg = 180/np.pi * np.arccos(np.dot(v1, v2)/ (np.linalg.norm(v1) * np.linalg.norm(v2)))
  return ang_deg

def make_FH_transform(F):
  assert F.GetNumberOfControlPoints()==3, "There must be exactly 3 fiducial points to reorient to FH, left ear canal, right ear canal, and left orbit base"
  FHpoints = []
  for idx in range(3):
    pos = [0,0,0]
    F.GetNthControlPointPositionWorld(idx,pos)
    FHpoints.append(pos)

  # Identify the orbit as the most anterior point
  ap_dimension_idx = 1 # RAS has A as the second dimension
  anterior_coordinates = [point[ap_dimension_idx] for point in FHpoints]
  orbit_idx = np.argmax(anterior_coordinates)
  orbit_point = FHpoints.pop(orbit_idx) # remove orbit point from list, leaving only ear points
  lr_dimension_idx = 0 # RAS has R as the first dimension
  right_coordinates = [p[lr_dimension_idx] for p in FHpoints]
  right_ear_idx = np.argmax(right_coordinates)
  right_ear_point = FHpoints.pop(right_ear_idx)
  left_ear_point = FHpoints.pop() # last remaining point must be left ear

  vectorA = np.subtract(orbit_point, right_ear_point)
  vectorB = np.subtract(orbit_point, left_ear_point)

  origNormal = np.cross(vectorA, vectorB)
  origNormal /= np.linalg.norm(origNormal)

  # Find rotation matrix that brings the original normal to the goal normal (bringing
  # all three points into a plane with normal [0,0,-1])
  goalNormal = np.array([0,0,-1])
  goalNormal = goalNormal/np.linalg.norm(goalNormal)

  import math
  from scipy.spatial.transform import Rotation

  rotation_axis = np.cross(origNormal,goalNormal)
  if np.linalg.norm(rotation_axis) > 1e-10:
    rotation_axis = rotation_axis/np.linalg.norm(rotation_axis) # normalize
    rotation_angle_radians = math.acos(np.dot(origNormal,goalNormal))
    rotvec = rotation_axis*rotation_angle_radians
    r1 = Rotation.from_rotvec(rotvec)
  else:
    # origNormal and goalNormal are very close to identical
    r1 = Rotation.identity()

  # Find intraplanar rotation 
  # This is the rotation necessary to move the vector pointing from
  # the right ear point to the left ear point to align with the direction
  # of the vector [-1,0,0]
  planarLtEar = r1.apply(left_ear_point)
  planarRtEar = r1.apply(right_ear_point)    
  planarLtoR = planarRtEar-planarLtEar
  planarLtoR = planarLtoR/np.linalg.norm(planarLtoR) # normalize
  LtoRGoal = [1,0,0]

  r2_rotation_axis = np.cross(planarLtoR,LtoRGoal) 
  # this cross product gives the perpedicular vector needed such that
  # right hand rotation around it by the acos value goes from the current
  # to the goal. This is why we don't need to worry about the sign of the 
  # angle returned by acos
  if np.linalg.norm(r2_rotation_axis)>1e-10:
    r2_rotation_axis = r2_rotation_axis/np.linalg.norm(r2_rotation_axis) #normalize
    r2_rotation_angle_radians = math.acos(np.dot(planarLtoR,LtoRGoal))
    rotvec2 = r2_rotation_axis*r2_rotation_angle_radians
    r2 = Rotation.from_rotvec(rotvec2)
  else: 
    r2 = Rotation.identity()

  rtot = r2*r1 # apply r1 then r2, r3 is the combined rotation

  # Make a transform from the calculated rotations
  transformName = 'points_FH_Transform'
  transNode = slicer.vtkMRMLLinearTransformNode()
  transNode.SetName(transformName)

  vtkRotMatrix = vtk.vtkMatrix4x4() # this will hold the rotation matrix
  rm3x3 = rtot.as_matrix()
  print('rm3x3='+str(rm3x3))
  for r in range(3):
    for c in range(3):
      vtkRotMatrix.SetElement(r,c,rm3x3[r,c])
  transNode.SetMatrixTransformToParent(vtkRotMatrix)
  slicer.mrmlScene.AddNode(transNode)
  return transNode

def sortByForGridNames(gridName):
  # if the grid name is Trajectory^# or Trajectory^##, sort by the number, otherwise, sort alphabetically
  patt = re.compile(r'Trajectory\^(\d\d?)') 
  foundGroup = re.search(patt,gridName)
  if foundGroup:
    # pattern was found, sort by number
    return int(foundGroup.group(1))
  else:
    # pattern not found, sort alphabetically by name
    return gridName


def parseDescriptionStr(descriptionStr):
  # parse the description string generated by BrainZoneDetector to get out the gray/white PTD value,
  # the primary anatomical label, and the full anatomical label

  # example description strings 
  # ' WM-hypointensities,86.0,Wm,14.0,PTD, 0.71'
  # ' Wm,100.0,PTD, -1.00'
  # ' Unk,100.0,PTD, 1.00'
  # ' Unk,86.0,ctx-lh-rostralmiddlefrontal,14.0,PTD, 1.00'
  # ' ctx-lh-insula,86.0,Wm,14.0,PTD, 0.71'

  # If query string is empty, return None for all outputs
  if len(descriptionStr)==0: 
    return None,None,None,None,None,None

  # The pattern has changed to:
  # GWULabel (Gray: X%, White: Y%, Unk: Z%); anatLabel1 (A1%), anatLabel2 (A2%),

  # The pattern is label,%, possibly repeated, followed by PTD, -?[1,0].\d\d
  anatPatt = re.compile(r'''(?P<withPct>
                        (?P<anat>
                          [a-zA-Z-]+ #letters and dashes
                        )
                        [ ]* # optional whitespace
                        [(]  # open paren
                        (?P<pct>  # group percentage digits
                          [0-9.]+  # digits or decimal point
                        )  
                        [%]   # percent sign
                        [)]   # close paren
                      )''', re.VERBOSE)

  g = re.findall(anatPatt,descriptionStr)
  if g is None:
    # this shouldn't really happen, maybe throw error here?
    pass
  numAnatLabels = len(g)
  anatLabels = []
  anatPcts = []
  for ind in range(numAnatLabels):
    anatLabels.append(g[ind][1])
    anatPcts.append(g[ind][2]) 
  AnatLabel1st = anatLabels[0]

  # Build multiline AnatLabelAll (label: pct% \n)
  AnatLabelAll = '\n'.join([label+':'+pct+'%' for label,pct in zip(anatLabels,anatPcts)])

  # Find GWU label ('Gray','White','Mixed','Unknown') and pct for each
  GWU_Patt = re.compile(r'''
    (?P<gwuLabel>
      [a-zA-Z]+  # upper and lowercase letters (no special characters, no white space)
    )
    [ ]*[(]Gray: # optional whitespace followed by open paren, followed by the exact string 'Gray:'
    [ ]*  # followed by optional whitespace
    (?P<grayPct>
      [0-9.]+ # followed by a decimal number, saved as grayPct
    )
    [%],[ ]* # followed by percent symbol, comma, and optional whitespace
    White:[ ]*
    (?P<whitePct>
      [0-9.]+ # followed by a decimal number, saved as whitePct
    )
    [%],[ ]*
    Unk:[ ]*
    (?P<unkPct>
      [0-9.]+ # followed by a decimal number, saved as unkPct
    )
    [%][)] # followed by percent symbol and close paren
    ''',re.VERBOSE)
  
  gwu_match = re.search(GWU_Patt,descriptionStr)
  GWULabel = gwu_match.group('gwuLabel')
  grayFrac = float(gwu_match.group('grayPct'))/100
  whiteFrac = float(gwu_match.group('whitePct'))/100
  unkFrac = float(gwu_match.group('unkPct'))/100



  return GWULabel,grayFrac,whiteFrac,unkFrac,AnatLabel1st,AnatLabelAll

def makeQBrush(namedColorStr,styleNum):
    # Convenience function for creating QBrush objects for coloring the background of table cells
    # namedColorStr can be any of the SVG named colors, styleNum is an integer 0-16 or 24. 
    # 0 is no brush pattern
    # 1 is solid
    # 2-8 are increasingly sparse brush patterns
    # 9 is horizontal lines, 10 is vertical lines, 11 is crossing horiz and vert lines
    # 12-14 are same for diagonal lines
    # 15-17 are gradient patterns (look up before using)
    # 24 is texture pattern (supply image to tile, look up before using)
    # https://doc.qt.io/qt-5/qt.html#BrushStyle-enum
    # Can also refer to by name like: qt.Qt.SolidPattern (for 1)
    #
    brush = qt.QBrush()
    color = qt.QColor()
    color.setNamedColor(namedColorStr)
    brush.setColor(color)
    brush.setStyle(styleNum)
    return brush
    


def brushFromGWULabel(gwuLabel):
    brush = qt.QBrush()
    label = gwuLabel.lower()
    if label == 'gray':
        brush = makeQBrush('gray',1) # 1 is solid
    if label == 'mixed':
        brush = makeQBrush('gray',6) # 6 is somewhat sparse
    if label == 'white':
        brush = makeQBrush('white',1) # 1 is solid
    if label == 'unk' or label == 'unknown':
        brush = makeQBrush('darkorchid',1)
    return brush


def brushFromPTDValue(PTDgrayVal,unkFrac=None):
    # PTDgrayVal is -1 for white, +1 for gray, and 0 for borderline
    # Returns qt.QBrush based on that value. 
    brush = qt.QBrush()
    #color = qt.QColor()
    if unkFrac and unkFrac>0.5:
        # Categorize as unknown, color purple
        brush = makeQBrush('darkorchid',1)
    elif PTDgrayVal< -0.3:
        # Categorize white
        brush = makeQBrush('white',1) # 1 is solid
    elif PTDgrayVal >=-.3 and PTDgrayVal<=0.3:
        # borderline
        brush = makeQBrush('gray',6) # 6 is somewhat sparse
    else: # PTDgrayVal > 0.3
        # Categorize gray matter
        brush = makeQBrush('gray',1) # 1 is solid
    return brush