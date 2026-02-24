# Phone Device - Technical Support Troubleshooting Workflow

## Introduction

This document provides a structured workflow for diagnosing and resolving phone technical issues. Follow these paths based on the user's problem description. Each step includes guidance on which specific troubleshooting action to perform based on what needs to be checked or modified.

Make sure you try all the relevant resolution steps before transferring the user to a human agent.

## Available User Actions Reference
Here are the actions a user is able to take on their device.
You must understand those well since as part of technical support you will have to help the customer perform series of actions

Agents should guide users to perform these specific actions as needed during troubleshooting:


### Diagnostic Actions (Read-only)
1. **Check Status Bar** - Shows what icons are currently visible in your phone's status bar (the area at the top of the screen). Displays network signal strength, mobile data status (enabled, disabled, data saver), Wi-Fi status, and battery level.
2. **Check Network Status** - Checks your phone's connection status to cellular networks and Wi-Fi. Shows airplane mode status, signal strength, network type, whether mobile data is enabled, and whether data roaming is enabled. Signal strength can be "none", "poor" (1bar), "fair" (2 bars), "good" (3 bars), "excellent" (4+ bars).
3. **Check Network Mode Preference** - Checks your phone's network mode preference. Shows the type of cellular network your phone prefers to connect to (e.g., 5G, 4G, 3G, 2G).
4. **Check SIM Status** - Checks if your SIM card is working correctly and displays its current status. Shows if the SIM is active, missing, or locked with a PIN or PUK code.
5. **Check Data Restrictions** - Checks if your phone has any data-limiting features active. Shows if Data Saver mode is on and whether background data usage is restricted globally.
6. **Check APN Settings** - Checks the technical APN settings your phone uses to connect to your carrier's mobile data network. Shows current APN name and MMSC URL for picture messaging.
7. **Check Wi-Fi Status** - Checks your Wi-Fi connection status. Shows if Wi-Fi is turned on, which network you're connected to (if any), and the signal strength.
8. **Check Wi-Fi Calling Status** - Checks if Wi-Fi Calling is enabled on your device. This feature allows you to make and receive calls over a Wi-Fi network instead of using the cellular network.
9. **Check VPN Status** - Checks if you're using a VPN (Virtual Private Network) connection. Shows if a VPN is active, connected, and displays any available connection details.
10. **Check Installed Apps** - Returns the name of all installed apps on the phone.
11. **Check App Status** - Checks detailed information about a specific app. Shows its permissions and background data usage settings.
12. **Check App Permissions** - Checks what permissions a specific app currently has. Shows if the app has access to features like storage, camera, location, etc.
13. **Run Speed Test** - Measures your current internet connection speed (download speed). Provides information about connection quality and what activities it can support. Download speed can be "unknown", "very poor", "poor", "fair", "good", or "excellent".
14. **Can Send MMS** - Checks if the messaging app can send MMS messages.

### Fix Actions (Write/Modify)
1. **Set Network Mode** - Changes the type of cellular network your phone prefers to connect to (e.g., 5G, 4G, 3G). Higher-speed networks (5G, 4G) provide faster data but may use more battery.
2. **Toggle Airplane Mode** - Turns Airplane Mode ON or OFF. When ON, it disconnects all wireless communications including cellular, Wi-Fi, and Bluetooth.
3. **Reseat SIM Card** - Simulates removing and reinserting your SIM card. This can help resolve recognition issues.
4. **Toggle Mobile Data** - Turns your phone's mobile data connection ON or OFF. Controls whether your phone can use cellular data for internet access when Wi-Fi is unavailable.
5. **Toggle Data Roaming** - Turns Data Roaming ON or OFF. When ON, roaming is enabled and your phone can use data networks in areas outside your carrier's coverage.
6. **Toggle Data Saver** - Turns Data Saver mode ON or OFF. When ON, it reduces data usage, which may affect data speed.
7. **Set APN Settings** - Sets the APN settings for the phone.
8. **Reset APN Settings** - Resets your APN settings to the default settings.
9. **Toggle Wi-Fi** - Turns your phone's Wi-Fi radio ON or OFF. Controls whether your phone can discover and connect to wireless networks for internet access.
10. **Toggle Wi-Fi Calling** - Turns Wi-Fi Calling ON or OFF. This feature allows you to make and receive calls over Wi-Fi instead of the cellular network, which can help in areas with weak cellular signal.
11. **Connect VPN** - Connects to your VPN (Virtual Private Network).
12. **Disconnect VPN** - Disconnects any active VPN (Virtual Private Network) connection. Stops routing your internet traffic through a VPN server, which might affect connection speed or access to content.
13. **Grant App Permission** - Gives a specific permission to an app (like access to storage, camera, or location). Required for some app functions to work properly.
14. **Reboot Device** - Restarts your phone completely. This can help resolve many temporary software glitches by refreshing all running services and connections.

## Initial Problem Classification

Determine which category best describes the user's issue:

1. **No Service/Connection Issues**: Phone shows "No Service" or cannot connect to the network
2. **Mobile Data Issues**: Cannot access internet or experiencing slow data speeds
3. **Picture/Group Messaging (MMS) Problems**: Unable to send or receive picture messages

For multiple issues, address basic connectivity first.

## Path 1: No Service / No Connection Troubleshooting

digraph TechSupportWorkflow {
    rankdir=TB;
    nodesep=0.7;
    node [fontname="Helvetica", fontsize=10, shape=rectangle];
    edge [fontname="Helvetica", fontsize=9];

    // Start and End Nodes
    Start [label="Start: User Reports Issue", shape=oval];
    End_Resolve [label="Issue Resolved", shape=oval];
    End_Escalate_Tech [label="Transfer to Human Agent", shape=oval];

    // Path 1: No Service / No Connection
    P1_Start [label="Path 1: No Service/Connection", shape=ellipse, style=filled, fillcolor=lightblue];
    P1_S0_CheckStatusBar [label="Step 1.0: Check if user is facing a no service issue", style=filled, fillcolor=lightblue];
    P1_S0_Decision_NoService [label="Status Bar shows\nno service/airplane mode?", shape=diamond];
    P1_S1_CheckAirplane [label="Step 1.1: Check Airplane Mode and Network Status", style=filled, fillcolor=lightblue];
    P1_S1_Decision_AirplaneON [label="Airplane Mode ON?", shape=diamond];
    P1_S1_Action_TurnAirplaneOFF [label="Ask user to turn Airplane Mode OFF"];
    P1_S1_Action_VerifyRestored1 [label="Ask user to look at their status bar\nand check if service is restored"];
    P1_S1_Decision_Restored1 [label="Service Restored?", shape=diamond];

    P1_S2_VerifySIM [label="Step 1.2: Verify SIM Card Status", style=filled, fillcolor=lightblue];
    P1_S2_Decision_SIMMissing [label="SIM Missing?", shape=diamond];
    P1_S2_Action_ReseatSIM [label="Ask user to re-seat the SIM card"];
    P1_S2_Action_VerifySIMImprove [label="Ask user to look at their status bar\nand check if service is restored"];
    P1_S2_Decision_SIMImproved [label="Service Restored?", shape=diamond];
    P1_S2_Decision_SIMLocked [label="SIM Locked (PIN/PUK)?", shape=diamond];

    P1_S3_ResetAPN [label="Step 1.3: Try to reset APN settings", style=filled, fillcolor=lightblue];
    P1_S3_User_Action_ResetAPN [label="Ask user to reset APN settings"];
    P1_S3_RestartDevice [label="Ask user to restart their device"];
    P1_S3_VerifyService [label="Ask user to look at their status bar\nand check if service is restored"];
    P1_S3_Decision_Resolved [label="Service Restored?", shape=diamond];

    // New Step 1.4: Check Line Suspension
    P1_S4_CheckSuspension [label="Step 1.4: Check Line Suspension", style=filled, fillcolor=lightblue];
    P1_S4_Decision_Suspended [label="Line Suspended?", shape=diamond];
    P1_S4_Decision_SuspensionType [label="Suspension Type?", shape=diamond];
    P1_S4_Decision_OverdueBill [label="Overdue Bill?", shape=diamond];
    P1_S4_Action_PaymentRequest [label="Send payment request\nfor overdue bill"];
    P1_S4_Action_CheckPayment [label="Ask user to check\npayment requests"];
    P1_S4_Action_MakePayment [label="Ask user to make\nthe payment"];
    P1_S4_Action_ResumeLine [label="Resume the line"];
    P1_S4_Action_Reboot [label="Ask user to reboot\ntheir device"];
    P1_S4_Action_VerifyService [label="Ask user to check\nif service is restored"];
    P1_S4_Decision_ServiceRestored [label="Service Restored?", shape=diamond];

    // Flow connections
    Start -> P1_Start;
    P1_Start -> P1_S0_CheckStatusBar;
    P1_S0_CheckStatusBar -> P1_S0_Decision_NoService;
    P1_S0_Decision_NoService -> P1_S1_CheckAirplane [label="Yes (No Service)"];
    P1_S0_Decision_NoService -> End_Resolve [label="No (Service Available)\nUser not facing no service issue"];

    P1_S1_CheckAirplane -> P1_S1_Decision_AirplaneON;
    P1_S1_Decision_AirplaneON -> P1_S1_Action_TurnAirplaneOFF [label="Yes"];
    P1_S1_Action_TurnAirplaneOFF -> P1_S1_Action_VerifyRestored1;
    P1_S1_Action_VerifyRestored1 -> P1_S1_Decision_Restored1;
    P1_S1_Decision_Restored1 -> End_Resolve [label="Yes"];
    P1_S1_Decision_Restored1 -> P1_S2_VerifySIM [label="No"];
    P1_S1_Decision_AirplaneON -> P1_S2_VerifySIM [label="No"];

    P1_S2_VerifySIM -> P1_S2_Decision_SIMMissing;
    P1_S2_Decision_SIMMissing -> P1_S2_Action_ReseatSIM [label="Yes"];
    P1_S2_Action_ReseatSIM -> P1_S2_Action_VerifySIMImprove;
    P1_S2_Action_VerifySIMImprove -> P1_S2_Decision_SIMImproved;
    P1_S2_Decision_SIMImproved -> P1_S3_ResetAPN [label="Yes (Service Restored)"];
    P1_S2_Decision_SIMImproved -> End_Escalate_Tech [label="No (Still No Service)"];
    P1_S2_Decision_SIMMissing -> P1_S2_Decision_SIMLocked [label="No"];

    P1_S2_Decision_SIMLocked -> End_Escalate_Tech [label="Yes"];
    P1_S2_Decision_SIMLocked -> P1_S3_ResetAPN [label="No (SIM Active)"];

    P1_S3_ResetAPN -> P1_S3_User_Action_ResetAPN;
    P1_S3_User_Action_ResetAPN -> P1_S3_RestartDevice;
    P1_S3_RestartDevice -> P1_S3_VerifyService;
    P1_S3_VerifyService -> P1_S3_Decision_Resolved;
    P1_S3_Decision_Resolved -> End_Resolve [label="Yes"];
    P1_S3_Decision_Resolved -> P1_S4_CheckSuspension [label="No"];

    // New Step 1.4 connections
    P1_S4_CheckSuspension -> P1_S4_Decision_Suspended;
    P1_S4_Decision_Suspended -> P1_S4_Decision_SuspensionType [label="Yes"];
    P1_S4_Decision_Suspended -> End_Escalate_Tech [label="No"];
    
    P1_S4_Decision_SuspensionType -> P1_S4_Decision_OverdueBill [label="Due to Bill"];
    P1_S4_Decision_SuspensionType -> End_Escalate_Tech [label="Due to Contract End"];
    
    P1_S4_Decision_OverdueBill -> P1_S4_Action_PaymentRequest [label="Yes"];
    P1_S4_Decision_OverdueBill -> P1_S4_Action_ResumeLine [label="No"];
    
    P1_S4_Action_PaymentRequest -> P1_S4_Action_CheckPayment;
    P1_S4_Action_CheckPayment -> P1_S4_Action_MakePayment;
    P1_S4_Action_MakePayment -> P1_S4_Action_ResumeLine;
    
    P1_S4_Action_ResumeLine -> P1_S4_Action_Reboot;
    P1_S4_Action_Reboot -> P1_S4_Action_VerifyService;
    P1_S4_Action_VerifyService -> P1_S4_Decision_ServiceRestored;
    
    P1_S4_Decision_ServiceRestored -> End_Resolve [label="Yes"];
    P1_S4_Decision_ServiceRestored -> End_Escalate_Tech [label="No"];
} 

## Path 2: Unavailable or Slow Mobile Data Troubleshooting

Note: This path does not cover wifi data issues.
digraph TechSupportWorkflow {
    rankdir=TB;
    nodesep=0.7;
    node [fontname="Helvetica", fontsize=10, shape=rectangle];
    edge [fontname="Helvetica", fontsize=9];

    // Start and End Nodes
    Start [label="Start: User Reports Issue", shape=oval];
    End_Resolve [label="Issue Resolved", shape=oval];
    End_Escalate_Tech [label="Transfer to Human Agent", shape=oval];

    // Path 2: Mobile Data Issues (Entry Point)
    P2_Start [label="Path 2: Mobile Data Issues", shape=ellipse, style=filled, fillcolor=lightgreen];
    P2_S0_RunSpeedTest [label="Step 2.0: Check if user is facing a data issue", style=filled, fillcolor=lightgreen];
    P2_S0_Decision_NoConnection [label="Speed Test shows\n'no connection'?", shape=diamond];
    P2_S0_Decision_ExcellentSpeed [label="Speed Test shows\n'Excellent'?", shape=diamond];

    // Path 2.1: Unavailable Mobile Data Troubleshooting
    P2_1_Start [label="Path 2.1: Unavailable Mobile Data", shape=ellipse, style=filled, fillcolor=coral];
    P2_1_S0_CheckUnavailableData [label="Step 2.1.0: Check if user is facing an unavailable mobile data issue", style=filled, fillcolor=coral];
    P2_1_S1_VerifyService [label="Step 2.1.1: Verify Service Issue", style=filled, fillcolor=coral];
    P2_1_Action_RetestAfterP1 [label="Ask user to rerun speed test\nafter Path 1 resolution"];
    P2_1_Decision_ConnectivityRestored [label="Data connectivity\nrestored?", shape=diamond];

    P2_1_S2_Decision_DataIssue [label="Step 2.1.2: Verify if user is traveling", shape=diamond];
    P2_1_S2_CheckRoaming [label="Check Roaming Settings", style=filled, fillcolor=coral];
    P2_1_S2_Decision_DataRoamingOFF [label="Data Roaming OFF?", shape=diamond];
    P2_1_S2_Action_TurnDataRoamingON [label="Ask user to turn Data Roaming ON"];
    P2_1_S2_Action_RetestAfterRoamingON [label="Ask user to rerun speed test"];
    P2_1_S2_Decision_RoamingWorksAfterON [label="Connectivity Restored?", shape=diamond];

    P2_1_S2_VerifyLineRoamingEnabled [label="Verify line is roaming enabled"];
    P2_1_S2_Decision_LineRoamingNotEnabled [label="Line not roaming enabled?", shape=diamond];
    P2_1_S2_Action_EnableRoaming [label="Enable roaming for user (no cost)"];
    P2_1_S2_Action_RetestAfterEnable [label="Ask user to rerun speed test"];
    P2_1_S2_Decision_RoamingWorksAfterEnable [label="Connectivity Restored?", shape=diamond];

    P2_1_S3_CheckMobileDataSettings [label="Step 2.1.3: Check Mobile Data Settings", style=filled, fillcolor=coral];
    P2_1_S3_Decision_MobileDataOFF [label="Mobile Data OFF?", shape=diamond];
    P2_1_S3_Action_TurnMobileDataON [label="Ask user to turn Mobile Data ON"];
    P2_1_S3_Action_RetestAfterMobileON [label="Ask user to rerun speed test"];
    P2_1_S3_Decision_MobileDataWorksAfterON [label="Connectivity Restored?", shape=diamond];

    P2_1_S4_CheckDataUsage [label="Step 2.1.4: Check Data Usage", style=filled, fillcolor=coral];
    P2_1_S4_Decision_DataExceeded [label="Data Usage Exceeded?", shape=diamond];
    P2_1_S4_Action_AskPlanOrRefuel [label="Ask user: change plan or refuel data?"];
    P2_1_S4_Decision_ChangePlan [label="Change Plan?", shape=diamond]; 
    P2_1_S4_Action_GatherPlans [label="Gather available plans"];
    P2_1_S4_Action_AskSelectPlan [label="Ask user to select a plan"]; 
    P2_1_S4_Action_ApplyPlan [label="Apply the plan"];
    P2_1_S4_Action_RefuelHowMuch [label="Ask how much data to refuel"];
    P2_1_S4_Action_ConfirmPrice [label="Confirm the price"];
    P2_1_S4_Decision_ConfirmRefuel [label="User Confirms Refuel?", shape=diamond]; 
    P2_1_S4_Action_ApplyRefuel [label="Apply the refueled data"];
    P2_1_S4_Action_RetestAfterDataAction [label="Ask user to rerun speed test"]; 
    P2_1_S4_Decision_ConnectivityAfterData [label="Connectivity Restored?", shape=diamond];
    P2_1_S4_Decision_ExcellentAfterData [label="Speed 'Excellent'?", shape=diamond];

    // Path 2.2: Slow Mobile Data Troubleshooting
    P2_2_Start [label="Path 2.2: Slow Mobile Data", shape=ellipse, style=filled, fillcolor=lightpink];
    P2_2_S0_CheckSlowData [label="Step 2.2.0: Check if user is facing a slow data issue", style=filled, fillcolor=lightpink];
    P2_2_S1_CheckDataRestriction [label="Step 2.2.1: Check Data Restriction Settings", style=filled, fillcolor=lightpink];
    P2_2_S1_Decision_DataSaverON [label="Data Saver ON?", shape=diamond];
    P2_2_S1_Action_TurnDataSaverOFF [label="Ask user to turn Data Saver mode OFF"];
    P2_2_S1_Action_RetestAfterSaver [label="Ask user to rerun speed test"];
    P2_2_S1_Decision_ExcellentAfterSaver [label="Speed 'Excellent'?", shape=diamond];

    P2_2_S2_CheckNetworkMode [label="Step 2.2.2: Check Network Mode Preference", style=filled, fillcolor=lightpink];
    P2_2_S2_Decision_OldNetworkMode [label="Set to older network (2G/3G)?", shape=diamond];
    P2_2_S2_Action_ChangeNetworkTo5G [label="Ask user to change network to include 5G"];
    P2_2_S2_Action_RetestAfterNetwork [label="Ask user to rerun speed test"];
    P2_2_S2_Decision_ExcellentAfterNetwork [label="Speed 'Excellent'?", shape=diamond];

    P2_2_S3_CheckVPN [label="Step 2.2.3: Check for Active VPN", style=filled, fillcolor=lightpink];
    P2_2_S3_Decision_VPNActive [label="VPN Active?", shape=diamond];
    P2_2_S3_Action_TurnVPNOFF [label="Ask user to turn off VPN"];
    P2_2_S3_Action_RetestAfterVPN [label="Ask user to rerun speed test"];
    P2_2_S3_Decision_ExcellentAfterVPN [label="Speed 'Excellent'?", shape=diamond];

    // Reference nodes for cross-path connections
    Path1_Reference [label="⚠️ Run Path 1: No Service\nTroubleshooting First", shape=rectangle, style="filled,dashed", fillcolor=lightblue];

    // Path 2 Entry Point Flow
    Start -> P2_Start;
    P2_Start -> P2_S0_RunSpeedTest;
    P2_S0_RunSpeedTest -> P2_1_Start;
    P2_S0_RunSpeedTest -> P2_2_Start;
    P2_1_Start -> P2_1_S0_CheckUnavailableData;
    P2_1_S0_CheckUnavailableData -> P2_S0_Decision_NoConnection;
    P2_2_Start -> P2_2_S0_CheckSlowData;
    P2_2_S0_CheckSlowData -> P2_S0_Decision_ExcellentSpeed;
    P2_S0_Decision_NoConnection -> P2_1_S1_VerifyService [label="Yes (No Connection)"];
    P2_S0_Decision_NoConnection -> P2_2_Start; 
    P2_S0_Decision_ExcellentSpeed -> End_Resolve [label="Yes (Not a data issue)"];
    P2_S0_Decision_ExcellentSpeed -> P2_2_S1_CheckDataRestriction [label="No (Slow data)"];

    // Path 2.1: Unavailable Mobile Data Flow
    P2_1_S1_VerifyService -> Path1_Reference [style=dashed, label="Follow Path 1"];
    P2_1_S1_VerifyService -> P2_1_Action_RetestAfterP1 [label="After Path 1 complete"];
    P2_1_Action_RetestAfterP1 -> P2_1_Decision_ConnectivityRestored;
    P2_1_Decision_ConnectivityRestored -> End_Resolve [label="Yes (Connectivity restored,\nspeed excellent)"];
    P2_1_Decision_ConnectivityRestored -> P2_2_Start [label="Yes (Connectivity restored\nbut speed not excellent)"];
    P2_1_Decision_ConnectivityRestored -> P2_1_S2_Decision_DataIssue [label="No"];

    P2_1_S2_Decision_DataIssue -> P2_1_S2_CheckRoaming [label="Yes"];
    P2_1_S2_Decision_DataIssue -> P2_1_S3_CheckMobileDataSettings [label="No"];

    P2_1_S2_CheckRoaming -> P2_1_S2_Decision_DataRoamingOFF;
    P2_1_S2_Decision_DataRoamingOFF -> P2_1_S2_Action_TurnDataRoamingON [label="Yes"];
    P2_1_S2_Action_TurnDataRoamingON -> P2_1_S2_Action_RetestAfterRoamingON;
    P2_1_S2_Action_RetestAfterRoamingON -> P2_1_S2_Decision_RoamingWorksAfterON;
    P2_1_S2_Decision_RoamingWorksAfterON -> End_Resolve [label="Yes (Connectivity restored,\nspeed excellent)"];
    P2_1_S2_Decision_RoamingWorksAfterON -> P2_2_Start [label="Yes (Connectivity restored\nbut speed not excellent)"];
    P2_1_S2_Decision_RoamingWorksAfterON -> P2_1_S2_VerifyLineRoamingEnabled [label="No"];
    P2_1_S2_Decision_DataRoamingOFF -> P2_1_S2_VerifyLineRoamingEnabled [label="No"];

    P2_1_S2_VerifyLineRoamingEnabled -> P2_1_S2_Decision_LineRoamingNotEnabled;
    P2_1_S2_Decision_LineRoamingNotEnabled -> P2_1_S2_Action_EnableRoaming [label="Yes"];
    P2_1_S2_Action_EnableRoaming -> P2_1_S2_Action_RetestAfterEnable;
    P2_1_S2_Action_RetestAfterEnable -> P2_1_S2_Decision_RoamingWorksAfterEnable;
    P2_1_S2_Decision_RoamingWorksAfterEnable -> End_Resolve [label="Yes (Connectivity restored,\nspeed excellent)"];
    P2_1_S2_Decision_RoamingWorksAfterEnable -> P2_2_Start [label="Yes (Connectivity restored\nbut speed not excellent)"];
    P2_1_S2_Decision_RoamingWorksAfterEnable -> P2_1_S3_CheckMobileDataSettings [label="No"];
    P2_1_S2_Decision_LineRoamingNotEnabled -> P2_1_S3_CheckMobileDataSettings [label="No"];

    P2_1_S3_CheckMobileDataSettings -> P2_1_S3_Decision_MobileDataOFF;
    P2_1_S3_Decision_MobileDataOFF -> P2_1_S3_Action_TurnMobileDataON [label="Yes"];
    P2_1_S3_Action_TurnMobileDataON -> P2_1_S3_Action_RetestAfterMobileON;
    P2_1_S3_Action_RetestAfterMobileON -> P2_1_S3_Decision_MobileDataWorksAfterON;
    P2_1_S3_Decision_MobileDataWorksAfterON -> End_Resolve [label="Yes (Connectivity restored,\nspeed excellent)"];
    P2_1_S3_Decision_MobileDataWorksAfterON -> P2_2_Start [label="Yes (Connectivity restored\nbut speed not excellent)"];
    P2_1_S3_Decision_MobileDataWorksAfterON -> P2_1_S4_CheckDataUsage [label="No"];
    P2_1_S3_Decision_MobileDataOFF -> P2_1_S4_CheckDataUsage [label="No"];

    P2_1_S4_CheckDataUsage -> P2_1_S4_Decision_DataExceeded;
    P2_1_S4_Decision_DataExceeded -> P2_1_S4_Action_AskPlanOrRefuel [label="Yes"];
    P2_1_S4_Action_AskPlanOrRefuel -> P2_1_S4_Decision_ChangePlan;
    P2_1_S4_Decision_ChangePlan -> P2_1_S4_Action_GatherPlans [label="Yes (Change Plan)"];
    P2_1_S4_Action_GatherPlans -> P2_1_S4_Action_AskSelectPlan;
    P2_1_S4_Action_AskSelectPlan -> P2_1_S4_Action_ApplyPlan;
    P2_1_S4_Action_ApplyPlan -> P2_1_S4_Action_RetestAfterDataAction;
    P2_1_S4_Decision_ChangePlan -> P2_1_S4_Action_RefuelHowMuch [label="No (Refuel Data)"];
    P2_1_S4_Action_RefuelHowMuch -> P2_1_S4_Action_ConfirmPrice;
    P2_1_S4_Action_ConfirmPrice -> P2_1_S4_Decision_ConfirmRefuel;
    P2_1_S4_Decision_ConfirmRefuel -> P2_1_S4_Action_ApplyRefuel [label="Yes"];
    P2_1_S4_Action_ApplyRefuel -> P2_1_S4_Action_RetestAfterDataAction;
    P2_1_S4_Action_RetestAfterDataAction -> P2_1_S4_Decision_ConnectivityAfterData;
    P2_1_S4_Decision_ConnectivityAfterData -> P2_1_S4_Decision_ExcellentAfterData [label="Yes"];
    P2_1_S4_Decision_ExcellentAfterData -> End_Resolve [label="Yes"];
    P2_1_S4_Decision_ExcellentAfterData -> P2_2_Start [label="No"];
    P2_1_S4_Decision_ConnectivityAfterData -> End_Escalate_Tech [label="No"];
    P2_1_S4_Decision_ConfirmRefuel -> End_Escalate_Tech [label="No (User declined refuel)"];
    P2_1_S4_Decision_DataExceeded -> End_Escalate_Tech [label="No (Data not exceeded)"];

    // Path 2.2: Slow Mobile Data Flow
    P2_2_S1_CheckDataRestriction -> P2_2_S1_Decision_DataSaverON;
    P2_2_S1_Decision_DataSaverON -> P2_2_S1_Action_TurnDataSaverOFF [label="Yes"];
    P2_2_S1_Action_TurnDataSaverOFF -> P2_2_S1_Action_RetestAfterSaver;
    P2_2_S1_Action_RetestAfterSaver -> P2_2_S1_Decision_ExcellentAfterSaver;
    P2_2_S1_Decision_ExcellentAfterSaver -> End_Resolve [label="Yes"];
    P2_2_S1_Decision_ExcellentAfterSaver -> P2_2_S2_CheckNetworkMode [label="No"];
    P2_2_S1_Decision_DataSaverON -> P2_2_S2_CheckNetworkMode [label="No"];

    P2_2_S2_CheckNetworkMode -> P2_2_S2_Decision_OldNetworkMode;
    P2_2_S2_Decision_OldNetworkMode -> P2_2_S2_Action_ChangeNetworkTo5G [label="Yes"];
    P2_2_S2_Action_ChangeNetworkTo5G -> P2_2_S2_Action_RetestAfterNetwork;
    P2_2_S2_Action_RetestAfterNetwork -> P2_2_S2_Decision_ExcellentAfterNetwork;
    P2_2_S2_Decision_ExcellentAfterNetwork -> End_Resolve [label="Yes"];
    P2_2_S2_Decision_ExcellentAfterNetwork -> P2_2_S3_CheckVPN [label="No"];
    P2_2_S2_Decision_OldNetworkMode -> P2_2_S3_CheckVPN [label="No"];

    P2_2_S3_CheckVPN -> P2_2_S3_Decision_VPNActive;
    P2_2_S3_Decision_VPNActive -> P2_2_S3_Action_TurnVPNOFF [label="Yes"];
    P2_2_S3_Action_TurnVPNOFF -> P2_2_S3_Action_RetestAfterVPN;
    P2_2_S3_Action_RetestAfterVPN -> P2_2_S3_Decision_ExcellentAfterVPN;
    P2_2_S3_Decision_ExcellentAfterVPN -> End_Resolve [label="Yes"];
    P2_2_S3_Decision_ExcellentAfterVPN -> End_Escalate_Tech [label="No"];
    P2_2_S3_Decision_VPNActive -> End_Escalate_Tech [label="No"];
} 

## Path 3: MMS (Picture/Group Messaging) Troubleshooting

digraph TechSupportWorkflow {
    rankdir=TB;
    nodesep=0.7;
    node [fontname="Helvetica", fontsize=10, shape=rectangle];
    edge [fontname="Helvetica", fontsize=9];

    // Start and End Nodes
    Start [label="Start: User Reports Issue", shape=oval];
    End_Resolve [label="Issue Resolved", shape=oval];
    End_Escalate_Tech [label="Transfer to Human Agent", shape=oval];
    
    // External Path References
    Path1_Reference [label="⚠️ Run Path 1: No Service\nTroubleshooting First", shape=rectangle, style="filled,dashed", fillcolor=lightblue];
    Path2_1_Reference [label="⚠️ Run Path 2.1: Mobile Data\nConnectivity Check", shape=rectangle, style="filled,dashed", fillcolor=coral];

    // Path 3: MMS Troubleshooting
    P3_Start [label="Path 3: MMS (Picture/Group Messaging)", shape=ellipse, style=filled, fillcolor=lightcoral];
    P3_S0_CheckMMS [label="Step 3.0: Check if user is facing a MMS issue", style=filled, fillcolor=lightcoral];
    P3_S0_Decision_MMSWorks [label="Can send MMS?", shape=diamond];

    P3_S1_VerifyNetworkService [label="Step 3.1: Verify Network Service Status", style=filled, fillcolor=lightcoral];
    P3_S1_Action_RetestMMS_P1 [label="Ask user to try MMS again\nafter Path 1 resolution"];

    P3_S2_VerifyMobileData [label="Step 3.2: Verify Mobile Data Status", style=filled, fillcolor=lightcoral];
    P3_S2_Action_RetestMMS_P2 [label="Ask user to try MMS again\nafter data connectivity confirmed"];

    P3_S3_CheckNetworkTech [label="Step 3.3: Check Network Technology", style=filled, fillcolor=lightcoral];
    P3_S3_Decision_Is2G [label="Connected to 2G only?", shape=diamond];
    P3_S3_Action_ChangeNetworkMode [label="Ask user to change network mode\nto include 3G/4G/5G"];
    P3_S3_Action_VerifyMMSWorks2G [label="Ask user to try MMS again"];
    P3_S3_Decision_MMSWorksAfter2G [label="MMS Works?", shape=diamond];

    P3_S4_CheckWifiCalling [label="Step 3.4: Check Wi-Fi Calling Status", style=filled, fillcolor=lightcoral];
    P3_S4_Decision_WifiCallingON [label="Wi-Fi Calling ON?", shape=diamond];
    P3_S4_Action_TurnWifiCallingOFF [label="Ask user to turn Wi-Fi Calling OFF"];
    P3_S4_Action_VerifyMMSWorksWifiOFF [label="Ask user to try MMS again"];
    P3_S4_Decision_MMSWorksAfterWifiOFF [label="MMS Works?", shape=diamond];

    P3_S5_VerifyAppPermissions [label="Step 3.5: Verify Messaging App Permissions", style=filled, fillcolor=lightcoral];
    P3_S5_Decision_PermissionsMissing [label="Storage or SMS permission missing?", shape=diamond];
    P3_S5_Action_GrantPermissions [label="Ask user to grant both permissions"];
    P3_S5_Action_VerifyMMSWorksPerms [label="Ask user to try MMS again"];
    P3_S5_Decision_MMSWorksAfterPerms [label="MMS Works?", shape=diamond];

    P3_S6_CheckAPNSettings [label="Step 3.6: Check APN Settings", style=filled, fillcolor=lightcoral];
    P3_S6_Decision_MMSC_Missing [label="MMSC URL missing?", shape=diamond];
    P3_S6_Action_ResetAPN [label="Ask user to reset APN settings to carrier defaults"];
    P3_S6_Action_VerifyMMSWorksAPN [label="Ask user to try MMS again"];
    P3_S6_Decision_MMSWorksAfterAPN [label="MMS Works?", shape=diamond];

    // Flow connections
    Start -> P3_Start;
    P3_Start -> P3_S0_CheckMMS;
    P3_S0_CheckMMS -> P3_S0_Decision_MMSWorks;
    P3_S0_Decision_MMSWorks -> End_Resolve [label="Yes (Not an MMS issue)"];
    P3_S0_Decision_MMSWorks -> P3_S1_VerifyNetworkService [label="No"];

    P3_S1_VerifyNetworkService -> Path1_Reference [style=dashed, label="Follow Path 1"];
    P3_S1_VerifyNetworkService -> P3_S1_Action_RetestMMS_P1 [label="After Path 1 confirms service"];
    P3_S1_Action_RetestMMS_P1 -> P3_S2_VerifyMobileData;

    P3_S2_VerifyMobileData -> Path2_1_Reference [style=dashed, label="Follow Path 2.1 (connectivity focus)"];
    P3_S2_VerifyMobileData -> P3_S2_Action_RetestMMS_P2 [label="After data connectivity confirmed"];
    P3_S2_Action_RetestMMS_P2 -> P3_S3_CheckNetworkTech;

    P3_S3_CheckNetworkTech -> P3_S3_Decision_Is2G;
    P3_S3_Decision_Is2G -> P3_S3_Action_ChangeNetworkMode [label="Yes"];
    P3_S3_Action_ChangeNetworkMode -> P3_S3_Action_VerifyMMSWorks2G;
    P3_S3_Action_VerifyMMSWorks2G -> P3_S3_Decision_MMSWorksAfter2G;
    P3_S3_Decision_MMSWorksAfter2G -> End_Resolve [label="Yes"];
    P3_S3_Decision_MMSWorksAfter2G -> P3_S4_CheckWifiCalling [label="No"];
    P3_S3_Decision_Is2G -> P3_S4_CheckWifiCalling [label="No (3G+)"];

    P3_S4_CheckWifiCalling -> P3_S4_Decision_WifiCallingON;
    P3_S4_Decision_WifiCallingON -> P3_S4_Action_TurnWifiCallingOFF [label="Yes"];
    P3_S4_Action_TurnWifiCallingOFF -> P3_S4_Action_VerifyMMSWorksWifiOFF;
    P3_S4_Action_VerifyMMSWorksWifiOFF -> P3_S4_Decision_MMSWorksAfterWifiOFF;
    P3_S4_Decision_MMSWorksAfterWifiOFF -> End_Resolve [label="Yes"];
    P3_S4_Decision_MMSWorksAfterWifiOFF -> P3_S5_VerifyAppPermissions [label="No"];
    P3_S4_Decision_WifiCallingON -> P3_S5_VerifyAppPermissions [label="No"];

    P3_S5_VerifyAppPermissions -> P3_S5_Decision_PermissionsMissing;
    P3_S5_Decision_PermissionsMissing -> P3_S5_Action_GrantPermissions [label="Yes"];
    P3_S5_Action_GrantPermissions -> P3_S5_Action_VerifyMMSWorksPerms;
    P3_S5_Action_VerifyMMSWorksPerms -> P3_S5_Decision_MMSWorksAfterPerms;
    P3_S5_Decision_MMSWorksAfterPerms -> End_Resolve [label="Yes"];
    P3_S5_Decision_MMSWorksAfterPerms -> P3_S6_CheckAPNSettings [label="No"];
    P3_S5_Decision_PermissionsMissing -> P3_S6_CheckAPNSettings [label="No"];

    P3_S6_CheckAPNSettings -> P3_S6_Decision_MMSC_Missing;
    P3_S6_Decision_MMSC_Missing -> P3_S6_Action_ResetAPN [label="Yes"];
    P3_S6_Action_ResetAPN -> P3_S6_Action_VerifyMMSWorksAPN;
    P3_S6_Action_VerifyMMSWorksAPN -> P3_S6_Decision_MMSWorksAfterAPN;
    P3_S6_Decision_MMSWorksAfterAPN -> End_Resolve [label="Yes"];
    P3_S6_Decision_MMSWorksAfterAPN -> End_Escalate_Tech [label="No"];
    P3_S6_Decision_MMSC_Missing -> End_Escalate_Tech [label="No"];
} 