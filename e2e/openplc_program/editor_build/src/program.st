PROGRAM main
  VAR
    last_seq : UINT := 65535;
  END_VAR
  VAR
    cmd_seq AT %QW0 : UINT;
    cmd_value AT %QW1 : UINT;
    ack_seq AT %QW2 : UINT;
    applied_value AT %QW3 : UINT;
    heartbeat AT %QW4 : UINT;
    applied_count AT %QW5 : UINT;
  END_VAR

  IF cmd_seq <> last_seq THEN
      last_seq := cmd_seq;
      applied_value := cmd_value;
      ack_seq := cmd_seq;
      applied_count := applied_count + 1;
    END_IF;

    heartbeat := heartbeat + 1;
END_PROGRAM


CONFIGURATION Config0

  RESOURCE Res0 ON PLC
    TASK task0(INTERVAL := T#10ms,PRIORITY := 1);
    PROGRAM instance0 WITH task0 : main;
  END_RESOURCE
END_CONFIGURATION
