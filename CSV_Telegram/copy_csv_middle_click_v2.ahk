#Requires AutoHotkey v2.0
#SingleInstance Force
SetTitleMatchMode 2

; Hold Shift + Middle Button to pass-through the default middle-click behavior
+MButton::
{
	Send "{MButton}"
}

; Main: middle button copies text under cursor in CSV-related windows
MButton::
{
	title := WinGetTitle("A")
	if !( InStr(title, ".csv")
		|| InStr(title, ".CSV")
		|| WinActive("ahk_exe EXCEL.EXE")
		|| WinActive("ahk_exe notepad.exe")
		|| WinActive("ahk_exe notepad++.exe")
		|| WinActive("ahk_exe Code.exe") )
	{
		return
	}

	; Clear clipboard first to avoid old data
	Clipboard := ""
	
	Click
	Sleep 10
	
	; Try to select cell content properly
	; For Excel and most editors, double-click or triple-click selects the cell/word
	if WinActive("ahk_exe EXCEL.EXE")
	{
		; In Excel, just clicking should be enough, then F2 or double-click to edit
		; But for copy, we can use Ctrl+C directly after clicking
		Send "^c"
	}
	else
	{
		; For text editors, triple-click to select the whole cell/line
		Click 3
		Sleep 10
		Send "^c"
	}
	
	; Wait for clipboard to update and verify it changed
	if !ClipWait(0.5)
	{
		ToolTip "Failed to copy"
		SetTimer(() => ToolTip(), -1000)
		return
	}
	
	; Small delay to ensure clipboard is fully synchronized
	Sleep 10
	
	; Read clipboard immediately as text
	copied := A_Clipboard
	
	; Verify we actually got new data (not empty)
	if !copied || (copied = "")
	{
		ToolTip "No text copied"
		SetTimer(() => ToolTip(), -1000)
		return
	}
	
	; Filter out common non-CSV patterns (commands, etc.)
	if InStr(copied, "pip install") || InStr(copied, "ERROR:") || InStr(copied, "python ") || InStr(copied, "SUCCESS:")
	{
		ToolTip "Skipped: not CSV data"
		SetTimer(() => ToolTip(), -1000)
		return
	}
	
	preview := copied
	if StrLen(preview) > 120
		preview := SubStr(preview, 1, 120) "…"
	ToolTip "Copied: " preview
	SetTimer(() => ToolTip(), -800)

	; Also send to Telegram bot chat via Python script (non-blocking)
	SendToTelegramPython(copied)
}

SendToTelegramPython(text)
{
	; Escape quotes in text for command line
	textEscaped := StrReplace(text, '"', '""')
	
	; Get Python path (try common locations)
	PythonExe := ""
	if FileExist("C:\Python311\python.exe")
		PythonExe := "C:\Python311\python.exe"
	else if FileExist("C:\Python310\python.exe")
		PythonExe := "C:\Python310\python.exe"
	else if FileExist("C:\Python39\python.exe")
		PythonExe := "C:\Python39\python.exe"
	else
		PythonExe := "python"
	
	scriptPath := A_ScriptDir "\send_to_telegram.py"
	if !FileExist(scriptPath)
	{
		ToolTip "ERROR: send_to_telegram.py not found"
		SetTimer(() => ToolTip(), -2000)
		return false
	}
	
	; Run Python script with text as argument (non-blocking, runs in background)
	; Use Run instead of RunWait so it doesn't block the next copy action
	Run '"' PythonExe '" "' scriptPath '" "' textEscaped '"', , "Hide"
	
	; Show feedback immediately (script runs in background)
	ToolTip "Sending to Telegram..."
	SetTimer(() => ToolTip(), -500)
	return true
}


