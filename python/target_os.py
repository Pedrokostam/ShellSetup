class AnyOs:
    def __str__(self) -> str:
        return "any" if type(self) is AnyOs else type(self).__name__.lower()

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AnyOs):
            return NotImplemented
        return str(self) == str(other)

    def __hash__(self) -> int:
        return hash(str(self))

    def get_more_generic_installers(self) -> list[str]:
        return [str(x()) for x in self._get_matching_system_classes() if x != type(self)]

    def _get_matching_system_classes(self):
        """
        Get all ancestor classes excluding object
        """
        return [cls for cls in type(self).mro() if cls is not object]

    def find_most_concrete_system(
        self, available_systems: list["AnyOs|None"]
    ) -> "AnyOs|None":
        for applicable_os in self._get_matching_system_classes():
            for system_for_app in available_systems:
                if isinstance(applicable_os(), type(system_for_app)):
                    return system_for_app
        return None


class Linux(AnyOs):
    pass


class Windows(AnyOs):
    pass


class Arch(Linux):
    pass


class Fedora(Linux):
    pass


class OpenSuse(Linux):
    pass


class Debian(Linux):
    pass


__ALL_OS = [Debian(), OpenSuse(), Fedora(), Arch(), Windows(), Linux(), AnyOs()]
CONCRETE_OS = [Debian(), OpenSuse(), Fedora(), Arch(), Windows()]


def get_system_from_string(s: str) -> AnyOs | None:
    s = s.lower()
    for os in __ALL_OS:
        if str(os) == s:
            return os
    return None
