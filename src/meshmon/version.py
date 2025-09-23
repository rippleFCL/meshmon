import semver


VERSION = "3.0.0"

SEMVER = semver.Version.parse(VERSION)

if __name__ == "__main__":
    print(VERSION)
