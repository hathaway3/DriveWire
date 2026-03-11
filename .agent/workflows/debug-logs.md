1. **Pull Logs**: // turbo
   `git pull`
2. **Read system.log**: Read last 100 lines.
3. **Filter**:
   - WiFi: grep `SYS:`/`WiFi`.
   - DriveWire: grep `DW:`.
   - SD: grep `SD:`.
4. **Check Reset**: Look for `Reset cause:` (1=Power, 3=WDT).
5. **Memory audit**: Check `Memory free:` for OOM.
