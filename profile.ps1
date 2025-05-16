# Load custom stuff for all hosts
$private:currentUserAllHosts = "$psscriptroot/profile_custom.ps1"
if(Test-Path $private:currentUserAllHosts){
	. $private:currentUserAllHosts
}
