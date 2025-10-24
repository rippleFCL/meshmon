import semver

VERSION = "4.0.0-beta.7"

SEMVER = semver.Version.parse(VERSION)

if __name__ == "__main__":
    print(VERSION)
