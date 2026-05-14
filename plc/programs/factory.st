PROGRAM FactorySimulation
  VAR
    (* Station A: Conveyor Belt *)
    Conv_Speed AT %QW0 : INT := 100;
    Conv_Load AT %QW1 : INT := 50;
    
    (* Station B: Robotic Arm *)
    Robot_X AT %QW2 : INT := 0;
    Robot_Y AT %QW3 : INT := 0;
    Robot_Z AT %QW4 : INT := 0;
    Servo_Temp AT %QW5 : INT := 30;
    
    (* Station C: Fluid Tank *)
    Tank_Level AT %QW6 : INT := 500;
    Tank_Pressure AT %QW7 : INT := 100;
    Flow_Rate AT %QW8 : INT := 20;

    (* System State *)
    System_On AT %QX0.0 : BOOL := TRUE;
    Alarm_Active AT %QX0.1 : BOOL := FALSE;
    E_STOP AT %QX0.2 : BOOL := FALSE;
    
    Counter : DINT := 0;
    Noise_Gen : INT := 0;
  END_VAR

  IF E_STOP THEN
    System_On := FALSE;
    Alarm_Active := TRUE;
  END_IF;

  IF System_On THEN
    Counter := Counter + 1;
    
    (* Simple Pseudo-Random Noise Generator *)
    Noise_Gen := ANY_TO_INT((Counter * 17 + 43) MOD 11) - 5;
    
    (* --- Station A: Conveyor --- *)
    Conv_Speed := 100 + Noise_Gen;
    IF (Counter MOD 20) = 0 THEN
      Conv_Load := 50 + ANY_TO_INT(Counter MOD 15);
    END_IF;

    (* --- Station B: Robotic Arm --- *)
    Robot_X := ANY_TO_INT((Counter * 5) MOD 100);
    Robot_Y := ANY_TO_INT((Counter * 7) MOD 100);
    Robot_Z := ANY_TO_INT((Counter * 3) MOD 50);
    
    (* Servo gets hot if moving fast *)
    IF (Counter MOD 10) = 0 THEN
      Servo_Temp := 30 + ANY_TO_INT(Counter MOD 20) + (Noise_Gen / 2);
    END_IF;

    (* --- Station C: Fluid Tank --- *)
    IF Tank_Level > 100 AND Flow_Rate > 0 THEN
       Tank_Level := Tank_Level - Flow_Rate / 10;
    ELSE
       Tank_Level := 500; (* Refill *)
    END_IF;
    Tank_Pressure := 100 + (Tank_Level / 10) + Noise_Gen;

    (* --- Anomaly Injection (Real-World Spikes) --- *)
    (* Inject a sudden pressure spike every ~300 cycles *)
    IF (Counter MOD 300) = 0 THEN
       Tank_Pressure := Tank_Pressure + 200; 
       Alarm_Active := TRUE;
    ELSIF Alarm_Active AND (Counter MOD 300) > 10 THEN
       Alarm_Active := FALSE;
    END_IF;

  ELSE
    Conv_Speed := 0;
    Flow_Rate := 0;
  END_IF;

END_PROGRAM

CONFIGURATION Config0
  RESOURCE Res0 ON PLC
    TASK TaskMain(INTERVAL := T#50ms, PRIORITY := 0);
    PROGRAM Inst0 WITH TaskMain : FactorySimulation;
  END_RESOURCE
END_CONFIGURATION
