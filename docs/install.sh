#!/usr/bin/env bash
# Yeti Agent Bootstrap Installer
#
# Usage:
#   curl -fsSL https://nikeGunn.github.io/yeti-agent/install.sh | bash
#
# For development testing:
#   curl -fsSL <raw-url> | YETI_AGENT_BRANCH=<branch-name> bash
#
# =============================================================================
# WINDOWS INSTALLATION NOTES
# =============================================================================
#
# Windows requires Git Bash to run this script. Install Git for Windows first:
#   winget install Git.Git
#
# Then run from PowerShell:
#   & "C:\Program Files\Git\bin\bash.exe" -c 'curl -fsSL https://nikeGunn.github.io/yeti-agent/install.sh | bash'
#
# KNOWN ISSUES AND SOLUTIONS:
#
# 1. Python 3.14+ not yet tested
#    - Use Python 3.11, 3.12, or 3.13
#    - Install: winget install Python.Python.3.13
#
# 2. ARM64 Windows (Surface Pro X, Snapdragon laptops)
#    - Install x64 Python: winget install Python.Python.3.13 --architecture x64
#
# 3. Multiple Python versions installed
#    - Windows uses the 'py' launcher, not 'python3.x' commands
#    - Solution: Uninstall unwanted versions, or set PY_PYTHON=3.13
#
# 4. Stale virtual environment
#    - Kill Python processes: taskkill /IM python.exe /F
#    - Delete old venv: Remove-Item -Recurse -Force "$env:USERPROFILE\.yeti-agent-env"
#
# 5. PATH not working in PowerShell after install
#    - Restart PowerShell for changes to take effect
#
# =============================================================================

set -e

# =============================================================================
# Configuration
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

VENV_DIR="$HOME/.yeti-agent-env"

# =============================================================================
# Logging functions
# =============================================================================

log_info() {
	echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
	echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
	echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
	echo -e "${RED}✗${NC} $1"
}

# =============================================================================
# Argument parsing
# =============================================================================

parse_args() {
	while [[ $# -gt 0 ]]; do
		case $1 in
			--help|-h)
				echo "Yeti Agent Installer"
				echo ""
				echo "Usage: install.sh [OPTIONS]"
				echo ""
				echo "Options:"
				echo "  --help, -h        Show this help"
				echo ""
				echo "Installs Python 3.11+ (if needed), uv, yeti-agent, and Chromium."
				exit 0
				;;
			*)
				log_warn "Unknown argument: $1 (ignored)"
				shift
				;;
		esac
	done
}

# =============================================================================
# Platform detection
# =============================================================================

detect_platform() {
	local os=$(uname -s | tr '[:upper:]' '[:lower:]')
	local arch=$(uname -m)

	case "$os" in
		linux*)
			PLATFORM="linux"
			;;
		darwin*)
			PLATFORM="macos"
			;;
		msys*|mingw*|cygwin*)
			PLATFORM="windows"
			;;
		*)
			log_error "Unsupported OS: $os"
			exit 1
			;;
	esac

	log_info "Detected platform: $PLATFORM ($arch)"
}

# =============================================================================
# Virtual environment helpers
# =============================================================================

get_venv_bin_dir() {
	if [ "$PLATFORM" = "windows" ]; then
		echo "$VENV_DIR/Scripts"
	else
		echo "$VENV_DIR/bin"
	fi
}

activate_venv() {
	local venv_bin=$(get_venv_bin_dir)
	if [ -f "$venv_bin/activate" ]; then
		source "$venv_bin/activate"
	else
		log_error "Virtual environment not found at $venv_bin"
		exit 1
	fi
}

# =============================================================================
# Python management
# =============================================================================

check_python() {
	log_info "Checking Python installation..."

	local py_candidates="python3.13 python3.12 python3.11 python3 python"
	local py_paths="/usr/bin/python3.11 /usr/local/bin/python3.11"

	for py_cmd in $py_candidates; do
		if command -v "$py_cmd" &> /dev/null; then
			local version=$($py_cmd --version 2>&1 | awk '{print $2}')
			local major=$(echo $version | cut -d. -f1)
			local minor=$(echo $version | cut -d. -f2)

			if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
				PYTHON_CMD="$py_cmd"
				log_success "Python $version found ($py_cmd)"
				return 0
			fi
		fi
	done

	for py_path in $py_paths; do
		if [ -x "$py_path" ]; then
			local version=$($py_path --version 2>&1 | awk '{print $2}')
			local major=$(echo $version | cut -d. -f1)
			local minor=$(echo $version | cut -d. -f2)

			if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
				PYTHON_CMD="$py_path"
				log_success "Python $version found ($py_path)"
				return 0
			fi
		fi
	done

	if command -v python3 &> /dev/null; then
		local version=$(python3 --version 2>&1 | awk '{print $2}')
		log_warn "Python $version found, but 3.11+ required"
	else
		log_warn "Python not found"
	fi
	return 1
}

install_python() {
	log_info "Installing Python 3.11+..."

	SUDO=""
	if [ "$(id -u)" -ne 0 ] && command -v sudo &> /dev/null; then
		SUDO="sudo"
	fi

	case "$PLATFORM" in
		macos)
			if command -v brew &> /dev/null; then
				brew install python@3.11
			else
				log_error "Homebrew not found. Install from: https://brew.sh"
				exit 1
			fi
			;;
		linux)
			if command -v apt-get &> /dev/null; then
				$SUDO apt-get update
				$SUDO apt-get install -y python3.11 python3.11-venv python3-pip
			elif command -v yum &> /dev/null; then
				$SUDO yum install -y python311 python311-pip
			else
				log_error "Unsupported package manager. Install Python 3.11+ manually."
				exit 1
			fi
			;;
		windows)
			log_error "Please install Python 3.11+ from: https://www.python.org/downloads/"
			exit 1
			;;
	esac

	if check_python; then
		log_success "Python installed successfully"
	else
		log_error "Python installation failed"
		exit 1
	fi
}

# =============================================================================
# uv package manager
# =============================================================================

install_uv() {
	log_info "Installing uv package manager..."

	if command -v uv &> /dev/null; then
		log_success "uv already installed"
		return 0
	fi

	curl -LsSf https://astral.sh/uv/install.sh | sh

	export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

	if command -v uv &> /dev/null; then
		log_success "uv installed successfully"
	else
		log_error "uv installation failed. Try restarting your shell and run the installer again."
		exit 1
	fi
}

# =============================================================================
# Yeti Agent installation
# =============================================================================

install_yeti_agent() {
	log_info "Installing yeti-agent..."

	if [ ! -d "$VENV_DIR" ]; then
		if [ -n "$PYTHON_CMD" ]; then
			uv venv "$VENV_DIR" --python "$PYTHON_CMD"
		else
			uv venv "$VENV_DIR" --python 3.11
		fi
	fi

	activate_venv

	YETI_AGENT_BRANCH="${YETI_AGENT_BRANCH:-${BROWSER_USE_BRANCH:-main}}"
	YETI_AGENT_REPO="${YETI_AGENT_REPO:-${BROWSER_USE_REPO:-NikeGunn/yeti-agent}}"
	log_info "Installing from GitHub: $YETI_AGENT_REPO@$YETI_AGENT_BRANCH"

	local tmp_dir=$(mktemp -d)
	git clone --depth 1 --branch "$YETI_AGENT_BRANCH" "https://github.com/$YETI_AGENT_REPO.git" "$tmp_dir"
	uv pip install "$tmp_dir"
	rm -rf "$tmp_dir"

	log_success "yeti-agent installed"
}

install_chromium() {
	log_info "Installing Chromium browser..."

	activate_venv

	local cmd="uvx playwright install chromium"
	if [ "$PLATFORM" = "linux" ]; then
		cmd="$cmd --with-deps"
	fi
	cmd="$cmd --no-shell"

	eval $cmd

	log_success "Chromium installed"
}

# =============================================================================
# PATH configuration
# =============================================================================

configure_path() {
	local shell_rc=""
	local bin_path=$(get_venv_bin_dir)
	local local_bin="$HOME/.local/bin"

	if [ -n "$BASH_VERSION" ]; then
		shell_rc="$HOME/.bashrc"
	elif [ -n "$ZSH_VERSION" ]; then
		shell_rc="$HOME/.zshrc"
	else
		shell_rc="$HOME/.profile"
	fi

	if grep -q "yeti-agent-env" "$shell_rc" 2>/dev/null; then
		log_info "PATH already configured in $shell_rc"
	else
		echo "" >> "$shell_rc"
		echo "# Yeti Agent" >> "$shell_rc"
		echo "export PATH=\"$bin_path:$local_bin:\$PATH\"" >> "$shell_rc"
		log_success "Added to PATH in $shell_rc"
	fi

	if [ "$PLATFORM" = "windows" ]; then
		configure_powershell_path
	fi
}

configure_powershell_path() {
	local scripts_path='\\.yeti-agent-env\\Scripts'
	local local_bin='\\.local\\bin'

	local current_path=$(powershell.exe -Command "[Environment]::GetEnvironmentVariable('Path', 'User')" 2>/dev/null | tr -d '\r')

	if echo "$current_path" | grep -q "yeti-agent-env"; then
		log_info "PATH already configured"
		return 0
	fi

	powershell.exe -Command "[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + \$env:USERPROFILE + '$scripts_path;' + \$env:USERPROFILE + '$local_bin', 'User')" 2>/dev/null

	if [ $? -eq 0 ]; then
		log_success "Added to Windows PATH: %USERPROFILE%\\.yeti-agent-env\\Scripts"
	else
		log_warn "Could not update PATH automatically. Add manually:"
		log_warn "  \$env:PATH += \";\$env:USERPROFILE\\.yeti-agent-env\\Scripts\""
	fi
}

# =============================================================================
# Validation
# =============================================================================

validate() {
	log_info "Validating installation..."

	activate_venv

	# Try yeti-agent first, fall back to browser-use
	if command -v yeti-agent &> /dev/null; then
		if yeti-agent doctor; then
			log_success "Installation validated successfully!"
			return 0
		fi
	elif command -v browser-use &> /dev/null; then
		if browser-use doctor; then
			log_success "Installation validated successfully!"
			return 0
		fi
	fi

	log_warn "Some checks failed. Run 'yeti-agent doctor' for details."
	return 1
}

# =============================================================================
# Print completion message
# =============================================================================

print_next_steps() {
	local shell_rc=".bashrc"
	if [ -n "$ZSH_VERSION" ]; then
		shell_rc=".zshrc"
	fi

	echo ""
	echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
	echo ""
	log_success "Yeti Agent installed successfully!"
	echo ""

	echo "Next steps:"
	if [ "$PLATFORM" = "windows" ]; then
		echo "  1. Restart PowerShell (PATH is now configured automatically)"
	else
		echo "  1. Restart your shell or run: source ~/$shell_rc"
	fi
	echo "  2. Try: yeti-agent open https://example.com"
	echo ""
	echo "  Quick start:"
	echo "    yeti-agent init              # Generate a starter template"
	echo "    yeti-agent doctor            # Check your setup"
	echo ""
	echo -e "  Documentation: ${CYAN}https://github.com/NikeGunn/yeti-agent${NC}"
	echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
	echo ""
}

# =============================================================================
# Main installation flow
# =============================================================================

main() {
	echo ""
	echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
	echo -e "  ${BOLD}Yeti Agent${NC} — AI Browser Automation"
	echo -e "  ${CYAN}Made in Nepal 🇳🇵${NC}"
	echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
	echo ""

	parse_args "$@"

	# Step 1: Detect platform
	detect_platform

	# Step 2: Check/install Python
	if ! check_python; then
		if [ ! -t 0 ]; then
			log_info "Python 3.11+ not found. Installing automatically..."
			install_python
		else
			read -p "Python 3.11+ not found. Install now? [y/N] " -n 1 -r < /dev/tty
			echo
			if [[ $REPLY =~ ^[Yy]$ ]]; then
				install_python
			else
				log_error "Python 3.11+ required. Exiting."
				exit 1
			fi
		fi
	fi

	# Step 3: Install uv
	install_uv

	# Step 4: Install yeti-agent
	install_yeti_agent

	# Step 5: Install Chromium
	install_chromium

	# Step 6: Configure PATH
	configure_path

	# Step 7: Validate
	validate

	# Step 8: Print next steps
	print_next_steps
}

main "$@"
