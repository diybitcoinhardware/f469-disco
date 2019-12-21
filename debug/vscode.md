# Visual Studio Code Configuration

Visual Studio Code (VS Code) is a handy and highly configured IDE allowing to integrate debug and build tasks for this project.
Here are the steps to setup working environment based on this IDE and OpenOCD debug server:

- [Visual Studio Code Configuration](#visual-studio-code-configuration)
  - [Install Visual Studio Code](#install-visual-studio-code)
    - [Needed Extensions](#needed-extensions)
  - [Install OpenOCD](#install-openocd)
  - [Create Configuration Files](#create-configuration-files)
    - [Debug configuration](#debug-configuration)
    - [Build tasks](#build-tasks)

## Install Visual Studio Code

Please follow the link <https://code.visualstudio.com> to obtain latest distributive and actual setup instruction for Visual Studio Code.

### Needed Extensions

To allow support of C/C++ code and hardware debugger integration the following extensions needs to be installed from Extension Marketplace:

- [C/C++ extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode.cpptools)
- [Cortex-Debug extension](https://marketplace.visualstudio.com/items?itemName=marus25.cortex-debug)

## Install OpenOCD

OpenOCD, Open On-Chip Debugger is a debug server for embedded processors / microcontrollers. It provides JTAG/SWD access from GDB (or directly with TCL scripts) to processors with ARM, MIPS and other popular core architectures. OpenOCD can be built from source or obtained as binaries for your platform. For more detailed information please visit official website: [openocd.org](http://openocd.org)

**Quick installation reference:**

Mac OS X users, using [Homebrew](https://brew.sh) package manager:

    brew install openocd

Linux Ubuntu/Debian users:

    apt-get install openocd

Windows users, using [Chocolatey](https://chocolatey.org) package manager:

    choco install openocd

## Create Configuration Files

In VS Code debug configuration and build tasks are defined with JSON files stored inside **.vscode** directory (project root directory). Because these settings are sometimes specific to user preferences and machine configuration, .vscode directory is excluded from version control. Default configuration files are provided inside **/debug/templates/** directory.

### Debug configuration

VS Code keeps debugging configuration information in a **launch.json** file located in a .vscode directory. Additional information can be found on VS Code resource: [Debugging](https://code.visualstudio.com/docs/editor/debugging).

Here is an example launch.json for OpenOCD:

    {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "Debug MicroPython VM",
                "cwd": "${workspaceRoot}",
                "executable": "./micropython/ports/stm32/build-STM32F469DISC/firmware.elf",
                "request": "launch",
                "type": "cortex-debug",
                "servertype": "openocd",
                "svdFile": "./debug/STM32F469.svd",
                "configFiles": [ "board/stm32f469discovery.cfg" ]
            }
        ]
    }

### Build tasks

VS Code allows to define custom build tasks in **tasks.json** keept in a .vscode directory. Additional information can be found on VS Code resource: [Integrate with External Tools via Tasks](https://code.visualstudio.com/Docs/editor/tasks).

Here is an example tasks.json defining the following tasks:

- Clean device build directory
- Debug build for device
- Release build for device
- Erase internal Flash (unbrick)

:wastebasket: **Clean device build directory** deletes any intermediate and output files from build directory.

:beetle: **Debug build for device** builds the firmware in Debug configuration leaving symbolic information and disabling optimizations. This is the default configuration activated by "Terminal | Run Build Task..." command or before each debug session in launched.

:factory: **Release build for device** builds the firmware in Release configuration with needed optimizations making executable code more compact and higher performing.

:warning: **Erase internal Flash (unbrick)** is an emergency recovery command invoking complete erase of microcontroller's Flash memory including internal file system of MicroPython.

    {
        "version": "2.0.0",
        "tasks": [
            {
                "label": "Clean device build directory",
                "type": "shell",
                "command": "make BOARD=STM32F469DISC USER_C_MODULES=../../../usermods clean",
                "options": {
                    "cwd": "${workspaceFolder}/micropython/ports/stm32"
                },
                "problemMatcher": [
                    "$gcc"
                ]
            },
            {
                "label": "Debug build for device",
                "type": "shell",
                "command": "make BOARD=STM32F469DISC USER_C_MODULES=../../../usermods DEBUG=1",
                "options": {
                    "cwd": "${workspaceFolder}/micropython/ports/stm32"
                },
                "problemMatcher": [
                    "$gcc"
                ],
                "group": {
                    "kind": "build",
                    "isDefault": true
                }
            },
            {
                "label": "Release build for device",
                "type": "shell",
                "command": "make BOARD=STM32F469DISC USER_C_MODULES=../../../usermods",
                "options": {
                    "cwd": "${workspaceFolder}/micropython/ports/stm32"
                },
                "group": "build",
            },
            {
                "label": "Erase internal Flash (unbrick)",
                "type": "shell",
                "command": "openocd -f board/stm32f469discovery.cfg -c \"init\" -c \"reset halt\" -c \"flash erase_sector 0 0 last\" -c \"shutdown\"",
                "problemMatcher": []
            }
        ]
    }
