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

    # Create or get the parameter node to store user choices
    self.parameterNode = self.getLogic().getParameterNode()
    pn = self.parameterNode

    # Switch to custom 6-view
    SEEGRLogic().activate6View()

    # Instantiate and connect widgets ...

    #
    # Input Fiducial selection
    #
    inputCollapsibleButton = ctk.ctkCollapsibleButton()
    inputCollapsibleButton.text = 'Input'
    self.layout.addWidget(inputCollapsibleButton)

    self.inputFormLayout = qt.QFormLayout(inputCollapsibleButton)

    self.electrodeFolderSelector = qt.QComboBox()
    self.electrodeFolderSelector.setMaxVisibleItems(20)
    self.electrodeFolderSelector.addItems(['Electrodes_Markups']) # hard-code known folder name #TODO: make this more flexible
    self.inputFormLayout.addRow("Choose Electrode Folder:",self.electrodeFolderSelector)



    """ self.fiducialSelector = slicer.qMRMLNodeComboBox()
    self.fiducialSelector.nodeTypes = ['vtkMRMLMarkupsFiducialNode']
    self.fiducialSelector.selectNodeUponCreation = False
    self.fiducialSelector.noneEnabled = True
    self.fiducialSelector.setMRMLScene(slicer.mrmlScene)
    self.inputFormLayout.addRow("Contact list: ",self.fiducialSelector) """
    
    # # Tied to volume:
    # # The image volume the coordinates in the fiducial selector are tied to
    # # (i.e. if a transform is applied to this volume, then the fiducial points should move!)
    # self.coordVolumeSelector = slicer.qMRMLNodeComboBox()
    # self.coordVolumeSelector.nodeTypes = ['vtkMRMLScalarVolumeNode'] # could also choose a transform??
    # self.coordVolumeSelector.noneEnabled = True
    # self.coordVolumeSelector.setMRMLScene(slicer.mrmlScene) #Ah, I think this tells it what scene it should look in to make it's list of scalar volume nodes
    # self.coordVolumeSelector.selectNodeUponCreation = False
    # self.inputFormLayout.addRow('Coord Relative To: ', self.coordVolumeSelector)

    self.buildTableButton = qt.QPushButton('Build Table')
    self.inputFormLayout.addRow(self.buildTableButton)

    self.loadFromFileButton = qt.QPushButton('Load From File')
    self.saveToFileButton = qt.QPushButton('Save To File')
    self.inputFormLayout.addRow(self.loadFromFileButton,self.saveToFileButton)


    #
    # Table (testing for now)
    #
    tableCollapsibleButton = ctk.ctkCollapsibleButton()
    tableCollapsibleButton.text = 'Contact Table'
    self.layout.addWidget(tableCollapsibleButton)

    self.tableFormLayout = qt.QFormLayout(tableCollapsibleButton)

    #
    # Image selection
    #
    imageCollapsibleButton = ctk.ctkCollapsibleButton()
    imageCollapsibleButton.text = 'Image Volume Selection'
    self.layout.addWidget(imageCollapsibleButton)

    self.imageFormLayout = qt.QFormLayout(imageCollapsibleButton)

    self.imageBaseSelector = slicer.qMRMLNodeComboBox()
    self.imageBaseSelector.nodeTypes = ['vtkMRMLScalarVolumeNode']
    self.imageBaseSelector.noneEnabled = True
    self.imageBaseSelector.showChildNodeTypes = True # not sure which I want here
    self.imageBaseSelector.setMRMLScene(slicer.mrmlScene) # not entirely sure what this does
    self.imageBaseSelector.setToolTip("Choose the Base Image Volume")
    self.imageFormLayout.addRow('Base Image:',self.imageBaseSelector)

    self.imageOverlaySelector = slicer.qMRMLNodeComboBox()
    self.imageOverlaySelector.nodeTypes = ['vtkMRMLScalarVolumeNode']
    self.imageOverlaySelector.noneEnabled = True
    self.imageOverlaySelector.showChildNodeTypes = True # not sure which I want here
    self.imageOverlaySelector.setMRMLScene(slicer.mrmlScene) # not entirely sure what this does
    self.imageOverlaySelector.setToolTip("Choose the Base Image Volume")
    self.imageFormLayout.addRow('Overlay Image:',self.imageOverlaySelector)

    
    # Base to overlay slider
    # Overlay opacity
    self.overlayOpacitySliderWidget = ctk.ctkSliderWidget()
    self.overlayOpacitySliderWidget.minimum = 0
    self.overlayOpacitySliderWidget.maximum = 1
    self.overlayOpacitySliderWidget.singleStep = 0.01
    #self.overlayOpacitySliderWidget.value = foregroundOpacity
    self.overlayOpacitySliderWidget.setToolTip("Opacity of overlay image, 0-100%")
    self.overlayOpacitySliderWidget.setDecimals(2) # don't need fractional percentages 
    self.imageFormLayout.addRow('Overlay Image Opacity:',self.overlayOpacitySliderWidget)

    # Parcellation image selector
    self.parcellationImageSelector = slicer.qMRMLNodeComboBox()
    self.parcellationImageSelector.nodeTypes = ['vtkMRMLLabelMapVolumeNode']
    self.parcellationImageSelector.noneEnabled = True
    self.parcellationImageSelector.setMRMLScene(slicer.mrmlScene) # not entirely sure what this does
    self.parcellationImageSelector.setToolTip("Choose the Parcellation Volume")
    self.imageFormLayout.addRow('Parcellation Volume:',self.parcellationImageSelector)

    # Parcellation opacity slider
    self.parcellationOpacitySliderWidget = ctk.ctkSliderWidget()
    self.parcellationOpacitySliderWidget.minimum = 0
    self.parcellationOpacitySliderWidget.maximum = 1
    self.parcellationOpacitySliderWidget.singleStep = 0.01
    #self.parcellationOpacitySliderWidget.value = foregroundOpacity
    self.parcellationOpacitySliderWidget.setToolTip("Opacity of parcellation, 0-100%")
    self.parcellationOpacitySliderWidget.setDecimals(2) # don't need fractional percentages 
    self.imageFormLayout.addRow('Parcellation Opacity:',self.parcellationOpacitySliderWidget)


    # Initialize
    # Initialize the selectors based on the "Red" slice
    sliceName='Red'
    redCompositeNode = slicer.app.layoutManager().sliceWidget(sliceName).sliceLogic().GetSliceCompositeNode()
    self.redCompositeNode = redCompositeNode # store for later use, this shouldn't go out of date
    # Base
    backgroundID = redCompositeNode.GetBackgroundVolumeID() # something like 'vtkMRMLScalarVolume3', or None
    self.imageBaseSelector.setCurrentNodeID(backgroundID)
    # Overlay
    foregroundID = redCompositeNode.GetForegroundVolumeID() # something like 'vtkMRMLScalarVolume3', or None
    foregroundOpacity = redCompositeNode.GetForegroundOpacity() # 0-1
    self.imageOverlaySelector.setCurrentNodeID(foregroundID)
    self.overlayOpacitySliderWidget.value = foregroundOpacity
    # Parcellation
    labelID = redCompositeNode.GetLabelVolumeID() # 'NULL' if empty, or something like 'vtkMRMLLabelMapVolumeNode1'
    if labelID and not labelID == 'NULL':
      self.parcellationImageSelector.setCurrentNodeID(labelID)
    labelOpacity = redCompositeNode.GetLabelOpacity()
    self.parcellationOpacitySliderWidget.value = labelOpacity
  
    ## Segmentation display is handled a bit differently, and should probably not be set or gotten from here

    # connections/callbacks
    #self.applyButton.connect('clicked(bool)', self.onApplyButton)
    #self.electrodeFolderSelector.connect('currentIndexChanged(int)',self.onElectrodeFolderChange)
    #self.fiducialSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onInputSelect)
    self.buildTableButton.connect('clicked(bool)',self.onBuildTableButtonClick)
    self.loadFromFileButton.connect('clicked(bool)',self.onLoadFromFileButtonClick)
    self.saveToFileButton.connect('clicked(bool)',self.onSaveToFileButtonClick)
    self.imageBaseSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onBaseImageSelect)
    self.imageOverlaySelector.connect('currentNodeChanged(vtkMRMLNode*)',self.onOverlayImageSelect)
    self.parcellationImageSelector.connect('currentNodeChanged(vtkMRMLNode*)',self.onParcellationImageSelect)
    
    self.overlayOpacitySliderWidget.connect('valueChanged(double)',self.overlayOpacitySliderChanged)
    self.parcellationOpacitySliderWidget.connect('valueChanged(double)',self.parcellationOpacitySliderChanged)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Preset parameters
    self.showSelectedContact = True

    self.updateGuiFromParameterNode() # if there is stuff in the parameter node, use it to reset selections
    self.updateParameterNodeFromGui() # if there wasn't stuff in the parameter node, fill it in

  def cleanup(self):
    pass

  def updateGuiFromParameterNode(self):
    # Use all settings in the parameter node to update the GUI display
    # If a setting is not present (i.e. empty string), then don't force any change
    parametersList = ['ElectrodeFolderSelectedItemText','TableBuiltFlag','baseImageSelectedId']
    pass

  def updateParameterNodeFromGui(self):
    # Anything the user has selected using the GUI should be placed into the 
    # parameter node so that it can be saved and restored.
    # Electrode Folder
    electrodeFolderSelectedItemText = self.electrodeFolderSelector.currentText
    self.parameterNode.SetParameter('ElectrodeFolderSelectedItemText',electrodeFolderSelectedItemText)
    # Flag for whether table is built
    # Table dimensions/info or rebuild table on load? (omit for now and rebuild on load, TODO?)
    # Current selected row and column  (could just handle this in the contact selection code...)
    # Base image selector

    # Overlay image selector
    # Overlay image opacity
    # Parcellation selector
    # Parcellation opacity slider value
    



  def onBaseImageSelect(self,volNode):
    if volNode is None:
      volID = None
    else:
      volID = volNode.GetID()
    SEEGRLogic().setAllSlicesBaseImage(volID)
    
  def onOverlayImageSelect(self,volNode):
    if volNode is None:
      volID = None
    else:
      volID = volNode.GetID()
    SEEGRLogic().setAllSlicesOverlayImage(volID)
  def onParcellationImageSelect(self,volNode):
    if volNode is None:
      volID = None
    else:
      volID = volNode.GetID()
    SEEGRLogic().setAllSlicesLabelImage(volID)

  def overlayOpacitySliderChanged(self,opacityVal):
    # Change the overlay (foreground) image opacity
    logic = SEEGRLogic()
    logic.setAllSlicesOverlayOpacity(opacityVal)
    
  def parcellationOpacitySliderChanged(self,opacityVal):
    logic = SEEGRLogic()
    logic.setAllSlicesParcellationOpacity(opacityVal)

  def onSaveToFileButtonClick(self):
    fileDlg = ctk.ctkFileDialog()
    fileDlgParent = None
    caption = "Save Data As..."
    if hasattr(self,'savedFileName'):
      startingDir = self.savedFileName
    else:
      startingDir = 'SEEGR.gridDict.json'
    fileFilter = 'JSON file (*.json)'
    savedFileName = fileDlg.getSaveFileName(fileDlgParent,caption,startingDir,fileFilter) # launches file open dialog 
    if savedFileName=='':
      return # canceled without choosing file
    else: 
      self.savedFileName = savedFileName 
      with open(self.savedFileName,'w') as f:
        json.dump(self.gridDict,f)

  def onLoadFromFileButtonClick(self):
    fileDlg = ctk.ctkFileDialog()
    fileDlgParent = None
    caption = "Load Data From..."
    if hasattr(self,'savedFileName'):
      startingDir = self.savedFileName
    else:
      startingDir = 'SEEGR.gridDict.json'
    fileFilter = 'JSON file (*.json)'
    savedFileName = fileDlg.getOpenFileName(fileDlgParent,caption,startingDir,fileFilter) # launches file open dialog 
    if savedFileName=='':
      return # canceled without choosing file
    else: 
      self.savedFileName = savedFileName 
      with open(self.savedFileName,'r') as f:
        if hasattr(self,'gridDict'):
          self.oldGridDictBeforeLoad = self.gridDict
        self.gridDict = json.load(f)
    # Build table from loaded data
    self.buildTableFromGridDict()
    # TODO: note that the table could now be out of sync with the curve nodes, this needs to be checked up on...
    
  def buildTableFromGridDict(self):
    if hasattr(self,'table'):
      # table already exists, it should be cleared out before updating
      while self.tableFormLayout.rowCount()>0:
        self.tableFormLayout.takeAt(0)

    # Create table from gridDict
    self.table = self.makeQTableWidget(self.gridDict)

    # Add it to the layout
    self.tableFormLayout.addRow(self.table)
    # Resize
    self.fitTableSize(self.table)

  def onBuildTableButtonClick(self):
    # Build/Rebuild table, based on current selection of electrode folder
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    sceneID = shNode.GetSceneItemID()
    #invalidItemID = slicer.vtkMRMLSubjectHierarchyNode.GetInvalidItemID()

    folder_name = self.electrodeFolderSelector.currentText
    electrodeFolderSubjectHierarchyID = shNode.GetItemChildWithName(sceneID,folder_name)
    childrenIDs = vtk.vtkIdList()
    shNode.GetItemChildren(electrodeFolderSubjectHierarchyID,childrenIDs)
    curve_node_list = [shNode.GetItemDataNode(childID) for childID in [childrenIDs.GetId(i) for i in range(childrenIDs.GetNumberOfIds())]]

    logic = SEEGRLogic()
    self.gridDict = logic.processCurveNodesToElectrodeDict(curve_node_list)

    self.buildTableFromGridDict()


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

  def makeQTableWidget(self,gridDict):
    gridNames = sorted(gridDict.keys(),key=sortByForGridNames)# uses custom sorting function (could use different ones for table selector if desired)

    numGrids = len(gridNames)
    numContacts = []
    # determin max # of contacts
    for gridName in gridNames:
      numContacts.append(len(gridDict[gridName].keys()))
    maxNumContacts = np.max(numContacts)

    table = qt.QTableWidget()
    rowCount = numGrids
    table.setRowCount(rowCount)
    colCount = maxNumContacts+1 #+1 for name column
    table.setColumnCount(colCount)

    # make list of contact numbers for column headers
    contacNumberStrs = [str(n) for n in range(maxNumContacts,0,-1)] # count down from max to 1 and convert to string
    colHeaders = ['Name']
    colHeaders.extend(contacNumberStrs)
    table.setHorizontalHeaderLabels(colHeaders)
    #table.setVerticalHeaderLabels(gridNames) # alternate approach, not currently used

    outsideBrainNamedColor = 'azure'
    outsideBrainBrush = makeQBrush(outsideBrainNamedColor,qt.Qt.SolidPattern)#DiagCrossPattern) 

    # Loop over the table entries, initializing, setting flags and colors, tooltips, etc
    for row in range(rowCount):
      gridName = gridNames[row]
      for col in range(colCount):

        cell = qt.QTableWidgetItem()
        table.setItem(row,col,cell) # fill in with table widget items
        if col==0:
          # Grid name column
          cell.setText(gridName)
          cell.setFlags(33) # enabled and selectable, but not editable (41 would allow drop onto)
        else:
          # Contact number column 
          contactNumStr = colHeaders[col] # pull directly from column header list
          cell.setFlags(33) # enabled and selectable, but not editable (41 would allow drop onto)
          # Determine if there is a corresponding contact for this number for this grid
          if contactNumStr in gridDict[gridName].keys():
            # Connect callback HERE
            #cell.connect('cellClicked(int,int)',lambda r,c: logic.cellSelected(table,r,c)) # lambda used to pass the table as additional argument
            # Color should be based on Gray/White/Unknown balance (as summarized in GWULabel?)
            if 'GWULabel' in gridDict[gridName][contactNumStr].keys():
              GWULabel = gridDict[gridName][contactNumStr]['GWULabel']
              brush = brushFromGWULabel(GWULabel)
              cell.setBackground(brush)
            else:
              # No GWU label stored, should probably put something else here (so it doesn't look like white matter entry)
              brush = makeQBrush('yellow',5) # half dense 
              # Set tooltip to anatomy label if available!
            if 'AnatLabelAll' in gridDict[gridName][contactNumStr].keys():
              cell.setToolTip(gridDict[gridName][contactNumStr]['AnatLabelAll'])
          else:
            # no contact here, color based on outside brain color
            cell.setBackground(outsideBrainBrush)
    logic = SEEGRLogic()
    table.connect('cellClicked(int,int)', self.onCellSelect) 
    return table

  def onCellSelect(self,row,col):
    logic = SEEGRLogic()
    # if self.coordVolumeSelector.currentNode() is not None:
    #   linkedVolume = self.coordVolumeSelector.currentNode()
    # else:
    #  linkedVolume = None
    linkedVolume = None
    contactPos = logic.cellSelected(self.table,row,col,self.gridDict,linkedVolume)
    
    if contactPos is None:
      return
    # otherwise, keep going

    # Also update selected fiducial
    # Create or update selected fiducial node (the orange one which is separate from the main list)
    if hasattr(self,'selectedContactFiducialNode'):
      # update
      self.selectedContactFiducialNode.SetNthFiducialPosition(0,contactPos[0],contactPos[1],contactPos[2])
    else:
      # Take over an existing one if it exists, create otherwise
      fiducialNodesList = slicer.util.getNodesByClass('vtkMRMLMarkupsFiducialNode')
      fiducialNodeNames = [fNode.GetName() for fNode in fiducialNodesList]
      if 'SelectedContact' in fiducialNodeNames:
        # Take it over
        self.selectedContactFiducialNode = slicer.util.getNode('SelectedContact')
      else:
        # create
        self.selectedContactFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
        self.selectedContactFiducialNode.SetName('SelectedContact')
        slicer.mrmlScene.AddNode(self.selectedContactFiducialNode)
        self.selectedContactFiducialNode.CreateDefaultDisplayNodes()
        self.selectedContactFiducialNode.AddFiducial(contactPos[0],contactPos[1],contactPos[2])
        # Set color and visibility
        displayNode = self.selectedContactFiducialNode.GetDisplayNode()
        self.selectedContactFiducialNode.SetNthFiducialVisibility(0,True)
        self.selectedContactFiducialNode.SetNthFiducialSelected(0,True)
        displayNode.SetSelectedColor(1,.5,0) # orange

    # Set visibility based on showSelectedContact flag
    self.selectedContactFiducialNode.SetNthFiducialVisibility(0,self.showSelectedContact)
    gridName = self.table.item(row,0).text()
    contactNumberStr = self.table.horizontalHeaderItem(col).text()
    displayName = gridName+'_'+contactNumberStr
    self.selectedContactFiducialNode.SetNthFiducialLabel(0,displayName)

    # Change properties of electrode with selected contact (show numbers and change selection)
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    sceneID = shNode.GetSceneItemID()
    folder_name = self.electrodeFolderSelector.currentText
    electrodeFolderSubjectHierarchyID = shNode.GetItemChildWithName(sceneID,folder_name)
    childrenIDs = vtk.vtkIdList()
    shNode.GetItemChildren(electrodeFolderSubjectHierarchyID,childrenIDs)
    curve_node_list = [shNode.GetItemDataNode(childID) for childID in [childrenIDs.GetId(i) for i in range(childrenIDs.GetNumberOfIds())]]
    for cn in curve_node_list:
      if cn.GetName() == gridName:
        # This is the selected one
        cn.GetDisplayNode().SetPointLabelsVisibility(1) # Turn on point labels
        selectedStateToDisplay = 0 # set each to unselected (this will change color)
      else:
        # Not selected one
        cn.GetDisplayNode().SetPointLabelsVisibility(0) # turn off point labels
        selectedStateToDisplay = 1 # set each to selected (this is the default)
      for i in range(cn.GetNumberOfControlPoints()):
        cn.SetNthControlPointSelected(i,selectedStateToDisplay)
    
    # Add Corner annotation of the Electrode name and Selected contact number
    lm = slicer.app.layoutManager()
    sliceViewNames = lm.sliceViewNames()
    textToAdd = '%s - %s'%(gridName,contactNumberStr)
    for sliceName in sliceViewNames:
      view = lm.sliceWidget(sliceName).sliceView()
      view.cornerAnnotation().SetText(vtk.vtkCornerAnnotation.UpperRight,textToAdd)
      view.cornerAnnotation().SetText(vtk.vtkCornerAnnotation.UpperLeft,textToAdd)
      textProperty = view.cornerAnnotation().GetTextProperty()
      textProperty.SetColor(0,1,1)
      view.forceRender()
    # Same for 3D view
    view=slicer.app.layoutManager().threeDWidget(0).threeDView()
    view.cornerAnnotation().SetText(vtk.vtkCornerAnnotation.UpperRight,textToAdd)
    view.cornerAnnotation().SetText(vtk.vtkCornerAnnotation.UpperLeft,textToAdd)
    textProperty = view.cornerAnnotation().GetTextProperty()
    textProperty.SetColor(0,1,1)
    view.forceRender()

    
  def resetForm(self):
    #while self.parametersFormLayout.rowCount()>0:
    #  self.parametersFormLayout.takeAt(0)
    while self.tableFormLayout.rowCount()>0:
      self.tableFormLayout.takeAt(0)

  # def onGridSelect(self):
  #   logic = SEEGRLogic()
  #   gridName = self.gridSelector.currentText
  #   if gridName=='--Select from below--':
  #     # TODO this should actually strip out the entries in the contact list, otherwise the gridName will cause an error when a new contact is selected
  #     return
    
  #   print "Selected grid named: "+gridName

  #   if gridName in self.gridDict:
  #     # create contact selector
  #     if hasattr(self,'contactSelector'):
  #       self.contactSelector.disconnect('currentIndexChanged(int)') # disconnect so that removing items won't trigger callbacks
  #       while self.contactSelector.count >0:
  #         self.contactSelector.removeItem(0)
  #     else:
  #       # create if it doesn't exist
  #       self.contactSelector = qt.QComboBox()
  #       self.contactSelector.setMaxVisibleItems(20)
  #       self.parametersFormLayout.addRow('Choose contact: ',self.contactSelector)
      
  #     contactStrings = self.gridDict[gridName].keys()
  #     contactStrings.sort(key=int) # sort by integer cast
  #     contactStrings.insert(0,'--Select from below--')
  #     self.contactSelector.addItems(contactStrings) 
  #     self.contactSelector.connect('currentIndexChanged(int)',self.onContactSelectorChoice)

  def onContactSelectorChoice(self):
    #print 'Selected contact #'+self.contactSelector.currentText+' from grid '+self.gridSelector.currentText

    gridName = self.gridSelector.currentText
    contactNumberStr = self.contactSelector.currentText
    if contactNumberStr=='--Select from below--':
      return None
    #parallelSliceNode = slicer.util.getNode('vtkMRMLSliceNodeParallel')
    #orthoSliceNode = slicer.util.getNode('vtkMRMLSliceNodeOrthogonal')

    offsetOrCenter = 'center'

    logic = SEEGRLogic()

    logic.jumpParaAndOrthoSlicesToContact(gridName,contactNumberStr,self.gridDict,offsetOrCenter)
    contactPos = self.gridDict[gridName][contactNumberStr]['Position']

    # Create or update selected fiducial node (the orange one which is separate from the main list)
    if hasattr(self,'selectedContactFiducialNode'):
      # update
      self.selectedContactFiducialNode.SetNthFiducialPosition(0,contactPos[0],contactPos[1],contactPos[2])
    else:
      # create
      self.selectedContactFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
      self.selectedContactFiducialNode.SetName('SelectedContact')
      slicer.mrmlScene.AddNode(self.selectedContactFiducialNode)
      self.selectedContactFiducialNode.CreateDefaultDisplayNodes()
      self.selectedContactFiducialNode.AddFiducial(contactPos[0],contactPos[1],contactPos[2])
      # Set color and visibility
      displayNode = self.selectedContactFiducialNode.GetDisplayNode()
      self.selectedContactFiducialNode.SetNthFiducialVisibility(0,True)
      self.selectedContactFiducialNode.SetNthFiducialSelected(0,True)
      displayNode.SetSelectedColor(1,.5,0) # orange

    # Set visibility based on showSelectedContact flag
    self.selectedContactFiducialNode.SetNthFiducialVisibility(0,self.showSelectedContact)
    displayName = gridName+'_'+contactNumberStr
    self.selectedContactFiducialNode.SetNthFiducialLabel(0,displayName)

  def getLogic(self):
    return SEEGRLogic()  

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
  def setAllSlicesOverlayOpacity(self,opacityVal):
    layoutManager = slicer.app.layoutManager()
    sliceNames = layoutManager.sliceViewNames()
    for sliceName in sliceNames:
      compositeNode = layoutManager.sliceWidget(sliceName).sliceLogic().GetSliceCompositeNode()
      compositeNode.SetForegroundOpacity(opacityVal)
  def setAllSlicesParcellationOpacity(self,opacityVal):
    layoutManager = slicer.app.layoutManager()
    sliceNames = layoutManager.sliceViewNames()
    for sliceName in sliceNames:
      compositeNode = layoutManager.sliceWidget(sliceName).sliceLogic().GetSliceCompositeNode()
      compositeNode.SetLabelOpacity(opacityVal)

  def setAllSlicesBaseImage(self,volumeID):
    for sliceName in slicer.app.layoutManager().sliceViewNames():
      slicer.app.layoutManager().sliceWidget(sliceName).sliceLogic().GetSliceCompositeNode().SetBackgroundVolumeID(volumeID)
  def setAllSlicesOverlayImage(self,volumeID):
    for sliceName in slicer.app.layoutManager().sliceViewNames():
      slicer.app.layoutManager().sliceWidget(sliceName).sliceLogic().GetSliceCompositeNode().SetForegroundVolumeID(volumeID)
  def setAllSlicesLabelImage(self,volumeID):
    for sliceName in slicer.app.layoutManager().sliceViewNames():
      slicer.app.layoutManager().sliceWidget(sliceName).sliceLogic().GetSliceCompositeNode().SetLabelVolumeID(volumeID)

  def activate6View(self):
    customLayout = """
      <layout type="vertical" split="true">
        <item>
        <layout type="horizontal">
          <item>
        <view class="vtkMRMLSliceNode" singletontag="Red">
          <property name="orientation" action="default">Axial</property>
            <property name="viewlabel" action="default">R</property>
          <property name="viewcolor" action="default">#77D0CF</property>
        </view>
          </item>
        <item>
        <view class="vtkMRMLSliceNode" singletontag="Yellow">
          <property name="orientation" action="default">Sagittal</property>
            <property name="viewlabel" action="default">Y</property>
          <property name="viewcolor" action="default">#EDD54C</property>
        </view>
        </item>
        <item>
        <view class="vtkMRMLSliceNode" singletontag="Green">
          <property name="orientation" action="default">Coronal</property>
            <property name="viewlabel" action="default">G</property>
          <property name="viewcolor" action="default">#6EB04B</property>
        </view>
        </item>
        </layout>
        </item>
        <item>
        <layout type="horizontal">
          <item>
        <view class="vtkMRMLSliceNode" singletontag="Parallel">
          <property name="orientation" action="default">Axial</property>
          <property name="viewlabel" action="default">ll</property>
          <property name="viewcolor" action="default">#59CBDA</property>
          <property name="viewgroup" action="default">1</property>
        </view>
        </item> 
          <item>
        <view class="vtkMRMLSliceNode" singletontag="Orthogonal">
          <property name="orientation" action="default">Axial</property>
          <property name="viewlabel" action="default">T</property>
          <property name="viewcolor" action="default">#A277D0</property>
          <property name="viewgroup" action="default">1</property>
        </view>
        </item> 
        <item>
        <view class="vtkMRMLViewNode" singletontag="1">
          <property name="viewlabel" action="default">1</property>
        </view>
        </item>
        </layout>
        </item>
      </layout>
      """
    # Built-in layout IDs are all below 100, so you can choose any large random number
    # for your custom layout ID.
    customLayoutId=503

    layoutManager = slicer.app.layoutManager()
    layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(customLayoutId, customLayout)                                     

    # Switch to the new custom layout 
    layoutManager.setLayout(customLayoutId)

    # Add button to layout selector toolbar for this custom layout (only if not already there)
    viewToolBar = slicer.util.mainWindow().findChild('QToolBar', 'ViewToolBar')
    layoutMenu = viewToolBar.widgetForAction(viewToolBar.actions()[0]).menu()
    existingLayoutTextList = [action.text for action in layoutMenu.actions()]
    customLayoutText = "Six View SEEG"
    if customLayoutText not in existingLayoutTextList:
      layoutSwitchActionParent = layoutMenu  # use `layoutMenu` to add inside layout list, use `viewToolBar` to add next the standard layout list
      layoutSwitchAction = layoutSwitchActionParent.addAction(customLayoutText) # add inside layout list
      layoutSwitchAction.setData(customLayoutId)
      layoutSwitchAction.setIcon(qt.QIcon(':Icons/LayoutThreeOverThreeView.png'))
      layoutSwitchAction.setToolTip('6-view SEEG layout')
      layoutSwitchAction.connect('triggered()', lambda layoutId = customLayoutId: slicer.app.layoutManager().setLayout(layoutId))


  def cellSelected(self,table,row,col,gridDict,linkedVolume):
    # callback for selected contact cell of table, should jump all the slices to the corresponding contact location
    # needs to catch if it doesn't actually correspond to a contact

    gridName = table.item(row,0).text() # this should always be valid
    contactNumStr = table.horizontalHeaderItem(col).text()
    if contactNumStr not in gridDict[gridName].keys():
      # not a contact entry to jump to
      return None

    contactPos = self.getContactPos(gridName,contactNumStr,gridDict)

    if linkedVolume is not None:
      # transform contact position according to any transforms applied to the linked volume
      linkedVolume.TransformPointToWorld(contactPos,contactPos) # applies transform to first input and returns the result in the second input
      

    self.jumpRYGSlicesToContact(contactPos)
    self.jumpParaAndOrthoSlicesToContact(gridName,contactNumStr,gridDict)

    return contactPos

  def getContactPos(self,gridName,contactNumber,gridDict):
    contactPos = gridDict[gridName][str(contactNumber)]['Position']
    return contactPos
  def jumpRYGSlicesToContact(self,contactPosition,offsetOrCenter='offset'):
    redNode = slicer.util.getNode('vtkMRMLSliceNodeRed')
    if offsetOrCenter.lower=='offset':
      redNode.SetJumpModeToOffset()
      redNode.JumpSliceByOffsetting(contactPosition[0],contactPosition[1],contactPosition[2])
    else:
      redNode.SetJumpModeToCentered()
      redNode.JumpSliceByCentering(contactPosition[0],contactPosition[1],contactPosition[2])
    redNode.JumpAllSlices(contactPosition[0],contactPosition[1],contactPosition[2])
    #yellowNode = slicer.util.getNode('vtkMRMLSliceNodeYellow')
    #greenNode = slicer.util.getNode('vtkMRMLSliceNodeGreen')

  def jumpParaAndOrthoSlicesToContact(self,gridName,contactNumber,gridDict,offsetOrCenter='center'):
    parallelSliceNode = slicer.util.getNode('vtkMRMLSliceNodeParallel')
    orthoSliceNode = slicer.util.getNode('vtkMRMLSliceNodeOrthogonal')
    contactPos = self.getContactPos(gridName,contactNumber,gridDict)
    
    gridVector,normalVector = self.parallelAndOrthoVectors(gridName,gridDict)
    
    self.setSlicePoseFromSliceNormalAndPosition(parallelSliceNode, normalVector, contactPos, offsetOrCenter)
    self.setSlicePoseFromSliceNormalAndPosition(orthoSliceNode,gridVector,contactPos,offsetOrCenter)  

  def parallelAndOrthoVectors(self,gridName,gridDict):
    # get grid entry and target points
    
    contactsDict = gridDict[gridName]
    targetPos = contactsDict['1']['Position']
    maxContactNum=0 # initialize
    for k in contactsDict.keys():
        maxContactNum = max(maxContactNum,int(k))
    maxContactNumStr = str(maxContactNum)
    entryPos = contactsDict[maxContactNumStr]['Position']
    
    # grid vector points to target
    gridVector = np.array(targetPos)-np.array(entryPos)
    # Other vector
    otherVector = np.array([0,1,0])
    parallelTol = 0.001
    # Check for parallel with gridVector
    unitGridVector = gridVector/np.linalg.norm(gridVector)
    if np.abs(unitGridVector[0])<parallelTol and np.abs(unitGridVector[2])<parallelTol:
        print('Grid Vector was too close to parallel with [0,1,0], switching to [1,0,0]')
        otherVector = np.array([1,0,0])
    # Normal vector
    normalVector = np.cross(otherVector,unitGridVector)
    
    # Return the vector along the grid and the selected vector normal to the grid
    return gridVector, normalVector

  def processCurveNodesToElectrodeDict(self,curve_node_list):
    gridDict = {}
    for cn in curve_node_list:
      gridName = cn.GetName()
      if gridName not in gridDict:
        gridDict[gridName] = {} # initialize dictionary if not present
        contactDict = gridDict[gridName]
      for cp_ind in range(cn.GetNumberOfControlPoints()):
        cp_label = cn.GetNthControlPointLabel(cp_ind)
        contactNumberStr = cp_label
        if contactNumberStr not in contactDict:
          contactDict[contactNumberStr] = {'Position':None, 'ListIndex':None}
        pos = [0,0,0] # pre-allocate
        cn.GetNthControlPointPositionWorld(cp_ind,pos)
        contactDict[contactNumberStr]['Position'] = pos
        contactDict[contactNumberStr]['ListIndex'] = cp_ind
        # Add any gray/white/anat processing here
        descriptionStr = cn.GetNthControlPointDescription(cp_ind)
        GWULabel,grayFrac,whiteFrac,unkFrac,AnatLabel1st,AnatLabelAll = parseDescriptionStr(descriptionStr)

        if GWULabel is not None:
          contactDict[contactNumberStr]['GWULabel'] = GWULabel
        if grayFrac is not None:
          contactDict[contactNumberStr]['GrayFrac'] = grayFrac
        if unkFrac is not None:
          contactDict[contactNumberStr]['WhiteFrac'] = whiteFrac
        if unkFrac is not None:
          contactDict[contactNumberStr]['UnkFrac'] = unkFrac

        # if grayPTD is not None:
        #   contactDict[contactNumberStr]['GrayPTD'] = grayPTD
        if AnatLabelAll is not None:
          contactDict[contactNumberStr]['AnatLabelAll'] = AnatLabelAll
        if AnatLabel1st is not None:
          contactDict[contactNumberStr]['AnatLabelFirst'] = AnatLabel1st
        

      
    return gridDict#,electrode_dict

  # def processFiducialsNode(self,fiducialsListNode):
  #   # Take in fiducials list and return processed versions organized in dictionaries by grid name and contact number
  #   # Returns gridDict, a nested dictionary with the grid name as the outermost key, the contact number (as a string)
  #   # as the next key, and either 'Position' or 'ListIndex' as the third key. The 'Position' entry contains the 
  #   # WorldCoordinate RAS position of the contact, and the 'ListIndex' entry has the index into the fiducialsListNode
  #   # list (so that it is easy to do things like control visibility or selectedness via, e.g., fiducialsListNode.SetNthFiducialVisibility(index,vis)
  #   #
  #   # gridDict[gridName][contactNumberStr]['Position']
  #   # gridDict[gridName][contactNumberStr]['ListIndex']
  #   # gridDict[gridName][contactNumberStr]['GrayPTD']
  #   # gridDict[gridName][contactNumberStr]['AnatLabel1st']
  #   # gridDict[gridName][contactNumberStr]['AnatLabelAll']
  # 
  #   gridDict = {} # dictionary to hold the contact positions organized by grid name and contact number
  #
  #   labelPattern = re.compile(r"""(.*) # electrode name
  #                             _ # underscore
  #                             (\d\d?) # one or two digit contact number""",re.VERBOSE) # verbose flag allows the comments and ignores intra-pattern whitespace
  # 
  #   for f_ind in range(fiducialsListNode.GetNumberOfFiducials()):
  #     # Get label
  #     label = fiducialsListNode.GetNthFiducialLabel(f_ind) # should possibly change to GetNthControlPointLabel(f_ind)
  #     # Split label into electrode part and contact number part
  #     foundGroups = re.search(labelPattern,label)
  #     gridName = foundGroups.group(1)
  #     contactNumberStr = foundGroups.group(2) # might as well keep as string
  #     # Find world RAS position of fiducial
  #     worldCoord4 = [0,0,0,0] # pre-allocate world coordinated variable (has homogeneous 4th coord)
  #     fiducialsListNode.GetNthFiducialWorldCoordinates(f_ind,worldCoord4) # assign worldCoord4 variable
  #
  #     # Get markup description string
  #     descriptionStr = fiducialsListNode.GetNthControlPointDescription(f_ind)
  #     #descriptionStr = fiducialsListNode.GetNthMarkupDescription(f_ind)
  #     # parse description string
  #     grayPTD,AnatLabel1st,AnatLabelAll,unkFrac = parseDescriptionStr(descriptionStr)
  #     contactDict[contactNumberStr]['GrayPTD'] = grayPTD
  #     contactDict[contactNumberStr]['AnatLabelAll'] = AnatLabelAll
  #     contactDict[contactNumberStr]['AnatLabelFirst'] = AnatLabel1st
  #     contactDict[contactNumberStr]['UnkFrac'] = unkFrac
  #   
  #     # Add to dictionaries
  #     if gridName not in gridDict:
  #       gridDict[gridName] = {} # initialize the contact dictionary if this is the first time hitting this grid
  #     
  #     contactDict = gridDict[gridName]
  #     if contactNumberStr not in contactDict:
  #       contactDict[contactNumberStr] = {'Position':None, 'ListIndex':None}
  #
  #     contactDict[contactNumberStr]['Position'] = worldCoord4[0:3]
  #     contactDict[contactNumberStr]['ListIndex'] = f_ind
  #     contactDict[contactNumberStr]['GrayPTD'] = grayPTD
  #     contactDict[contactNumberStr]['AnatLabelAll'] = AnatLabelAll
  #     contactDict[contactNumberStr]['AnatLabelFirst'] = AnatLabel1st
  #     contactDict[contactNumberStr]['UnkFrac']
  #    
  #   # return the dictionary
  #   return gridDict
  
  def setSlicePoseFromSliceNormalAndPosition(self,sliceNode, sliceNormal, slicePosition, offsetOrCenter='center'):
    """
    Set slice pose from the provided plane normal and position. The most similar canonical view (sagittal, coronal, 
    or axial) is determined by the direction of the sliceNormal.  For example, if the largest component of the 
    sliceNormal is in the superior direction (or negative superior direction), then the most similar canonical view
    is the axial view. Care is taken to not allow misleading views, such as an axial-appearing view which has the 
    patient's right on the right hand side (reversed from the standard axial view). If the supplied normal would 
    naturally lead to such a misleading view, it is negated. 
    :param offsetOrCenter should be either 'offset' or 'center', and is used to determine whether the view should 
    be shifed to the given slicePosition by jumping by offsetting or by centering (using sliceNode.JumpSlicesByOffsetting
    or sliceNode.JumpSlicesByCentering, respectively).   
    """
    # Ensure sliceNormal is numpy array
    sliceNormal = np.array(sliceNormal)
    
    # Find largest and smallest components of sliceNormal
    largestComponentAxis = np.argmax(np.abs(sliceNormal)) # used to determine most similar view
    smallestComponentAxis = np.argmin(np.abs(sliceNormal)) # used to decide which of the slice X or Y axes to precisely align
    
    if largestComponentAxis==smallestComponentAxis:
        raise ValueError('Largest and smallest slice normal components are the same!!')
    
    viewLookup = {0: 'sagittal',
             1: 'coronal',
             2: 'axial'}
    
    mostSimilarView = viewLookup[largestComponentAxis]
    #print mostSimilarView
        
    # In order to make the adjusted view as similar as possible to a standard view, it may be necessary to use
    # the negation of the given slice normal rather than the given slice normal.  
    
    # The cross product relationships among the 3 axes are
    # Y = NxX, X = YxN, N = XxY  (where x means vector cross product here, recall that order matters)
    
    # In each of the mostSimilarView cases which follow, we 
    # 1) use the sign of the largest component to determine whether the sliceNormal needs to be negated 
    #    to more closely conform to the corresponding canonical view, 
    # 2) use the smallest component to determine which of the remaining axes is closer to lying in the new slice view 
    #    plane. The smaller the component in the direction of the sliceNormal, the larger the component must be in 
    #    the orthogonal plane.
    # 3) set the direction of the slice X axis so that the projection of the most in-plane of the R,A, or S axes 
    #    points precisely in the correct direction. If it is the new Y axis which is to be aligned, the X axis direction
    #    is determined by finding the cross product of the Y axis with the sliceNormal. 
    # 
    # Note that we can handle the normalization to unit vectors later, so if we want the slice Y axis to align as closely
    # as possible to the Superior axis, we can assign sliceAxisY to be [0,0,1] for now, even if the sliceNormal guarantees
    # that the vector [0,0,1] is not in the slice plane. After the cross products and normalization, the sliceAxisY

    if mostSimilarView=='sagittal':
        # Canonical view is image up is superior, image right is posterior, and patient right points out of screen
        if sliceNormal[largestComponentAxis]>0:
            sliceNormal = -sliceNormal # invert the normal if it would lead the Right axis to point into the screen
        if smallestComponentAxis==2:
            # if superior is closest to in-plane, say that up should be superior
            sliceAxisY = [0,0,1]
            sliceAxisX = np.cross(sliceAxisY,sliceNormal)
            #print 'up should be superior'
        elif smallestComponentAxis==1:
            # if right is closest to in-plane, say that right should be posterior
            sliceAxisX = [0,-1,0]
            #print 'right should be posterior'
        
    elif mostSimilarView=='coronal':
        # Canonical view is image up is superior, image right is patient left, and anterior points into the screen
        if sliceNormal[largestComponentAxis]<0:
            sliceNormal = -sliceNormal # invert the normal if it would lead the anterior axis to point out of the screen        
        if smallestComponentAxis==2:
            # if superior is closest to in-plane, say that up should be superior
            sliceAxisY = [0,0,1]
            sliceAxisX = np.cross(sliceAxisY,sliceNormal)
            #print('up should be superior')
        elif smallestComponentAxis==0:
            # if right is closest to in-plane, say that right should be left
            sliceAxisX = [-1,0,0]
            #print 'right should be patient left'
        
    elif mostSimilarView=='axial':
        # Canonical view is image up is anterior and image right is left
        if sliceNormal[largestComponentAxis]>0:
            sliceNormal=-sliceNormal # invert the normal if it would lead the Superior axis to point into the screen        
        if smallestComponentAxis==1:
            # if anterior is closest to in-plane, say that up should be anterior
            sliceAxisY = [0,1,0]
            sliceAxisX = np.cross(sliceAxisY,sliceNormal)
            #print 'up should be anterior'+' sliceAxisX='+str(sliceAxisX)
        elif smallestComponentAxis==0:
            # if right is closest to in-plane, say that right should be left
            sliceAxisX = [-1,0,0]
            #print 'right should be patient left'+' sliceAxisX='+str(sliceAxisX)
        
    else:
        # Should throw error here
        raise ValueError('mostSimilarView must be axial, coronal, or sagittal, but is "'+mostSimilarView+'"')
    
    
    vtkSliceToRAS = sliceNode.GetSliceToRAS()
    oldPosition = [vtkSliceToRAS.GetElement(0,3),
                   vtkSliceToRAS.GetElement(1,3),
                   vtkSliceToRAS.GetElement(2,3)]
    
    # In the new SliceToRAS matrix, sliceAxisX should be the first column, sliceAxisY should be the second column, 
    # and the normal vector should be the third colum (sliceAxisZ).  These should all be normalized and orthogonal.
    
    # SetSliceToRASByNTP handles this by 1) normalizing the input N and T vectors (slice normal and sliceAxisX),
    # 2) crossing them to generate sliceAxisY, and then 3) crossing the slice normal and sliceAxisY to generate
    # an updated version of sliceAxisX which is guaranteed to be orthogonal to both sliceAxisY and the slice normal. 
    
    sliceNormal = np.array(sliceNormal)
    magNormal = np.linalg.norm(sliceNormal)
    sliceNormal = sliceNormal/magNormal # normalize
    
    sliceAxisX = np.array(sliceAxisX)
    magSliceAxisX = np.linalg.norm(sliceAxisX)
    sliceAxisX = sliceAxisX/magSliceAxisX
    
    sliceAxisY = np.cross(sliceNormal,sliceAxisX) # Y = NxX (recall that order matters for cross products)
    magSliceAxisY = np.linalg.norm(sliceAxisY)
    sliceAxisY = sliceAxisY/magSliceAxisY # normalize
    
    sliceAxisX = np.cross(sliceAxisY,sliceNormal) # X = YxN (this order ensures X points in the same general direction as the original X, but is guaranteed to be orthogonal)
    magSliceAxisX = np.linalg.norm(sliceAxisX)
    
    # Set the elements of the SliceToRAS matrix
    for rowInd in range(3):
        vtkSliceToRAS.SetElement(rowInd,0,sliceAxisX[rowInd])
        vtkSliceToRAS.SetElement(rowInd,1,sliceAxisY[rowInd])
        vtkSliceToRAS.SetElement(rowInd,2,sliceNormal[rowInd])
        if offsetOrCenter.lower()=='center':
            # use the requested position as the slice center position
            vtkSliceToRAS.SetElement(rowInd,3,slicePosition[rowInd])
            
    
    sliceNode.UpdateMatrices() # This applies the changes to the SliceToRAS matrix
    
    if offsetOrCenter.lower()=='offset':
        # keep the original slice center position, but then adjust offset until it contains requested position
        sliceNode.JumpSliceByOffsetting(slicePosition[0],slicePosition[1],slicePosition[2])
    elif offsetOrCenter.lower()=='center':
        sliceNode.JumpSliceByCentering(slicePosition[0],slicePosition[1],slicePosition[2])


  def run(self, inputVolume, outputVolume, imageThreshold, enableScreenshots=0):
    """
    Run the actual algorithm
    """

    if not self.isValidInputOutputData(inputVolume, outputVolume):
      slicer.util.errorDisplay('Input volume is the same as output volume. Choose a different output volume.')
      return False

    logging.info('Processing started')

    # Compute the thresholded output volume using the Threshold Scalar Volume CLI module
    cliParams = {'InputVolume': inputVolume.GetID(), 'OutputVolume': outputVolume.GetID(), 'ThresholdValue' : imageThreshold, 'ThresholdType' : 'Above'}
    cliNode = slicer.cli.run(slicer.modules.thresholdscalarvolume, None, cliParams, wait_for_completion=True)

    # Capture screenshot
    if enableScreenshots:
      self.takeScreenshot('SEEGRTest-Start','MyScreenshot',-1)

    logging.info('Processing completed')

    return True



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