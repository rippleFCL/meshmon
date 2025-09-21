import semver


VERSION = "2.1.0"

SEMVER = semver.Version.parse(VERSION)

if __name__ == "__main__":
    print(VERSION)
