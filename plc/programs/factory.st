PROGRAM FactorySimulation
  VAR
    Motor_Temp AT %QW0 : INT := 25;  (* Holding Register 0 *)
    Motor_RPM AT %QW1 : INT := 0;   (* Holding Register 1 *)
    Vibration AT %QW2 : INT := 5;   (* Holding Register 2 *)
    Current AT %QW3 : INT := 0;     (* Holding Register 3 *)
    
    Motor_On AT %QX0.0 : BOOL := FALSE; (* Coil 0 *)
    Alarm_Active AT %QX0.1 : BOOL := FALSE; (* Coil 1 *)
    
    Counter : DINT := 0;
    Cycle_Time : TIME := T#50ms;
  END_VAR

  (* Logic for Motor Simulation *)
  IF Motor_On THEN
    Counter := Counter + 1;
    
    (* RPM fluctuates around 1750 *)
    Motor_RPM := 1750 + (ANY_TO_INT(Counter MOD 25) - 12);
    
    (* Temperature rises towards 75C *)
    IF Motor_Temp < 75 THEN
        IF (Counter MOD 20) = 0 THEN
            Motor_Temp := Motor_Temp + 1;
        END_IF;
    END_IF;
    
    (* Vibration simulation (increased vibration if hot) *)
    Vibration := 5 + (Motor_Temp / 20) + (ANY_TO_INT(Counter MOD 3));
    
    (* Current simulation: ~5.5A *)
    Current := 55 + (ANY_TO_INT(Counter MOD 5));

    (* Overheat Protection *)
    IF Motor_Temp > 85 THEN
        Alarm_Active := TRUE;
        Motor_On := FALSE; (* Emergency Stop *)
    ELSE
        Alarm_Active := FALSE;
    END_IF;

  ELSE
    (* Motor is OFF *)
    Motor_RPM := 0;
    Current := 0;
    Vibration := 2;
    
    (* Cooling down *)
    IF Motor_Temp > 25 THEN
      IF (Counter MOD 50) = 0 THEN
        Motor_Temp := Motor_Temp - 1;
      END_IF;
    END_IF;
    
    Counter := Counter + 1;
  END_VAR
END_PROGRAM

CONFIGURATION Config0
  RESOURCE Res0 ON PLC
    TASK TaskMain(INTERVAL := T#50ms, PRIORITY := 0);
    PROGRAM Inst0 WITH TaskMain : FactorySimulation;
  END_RESOURCE
END_CONFIGURATION
