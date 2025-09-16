# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.4.0] - 2025-09-16
### :sparkles: New Features
- [`accedc5`](https://github.com/rippleFCL/meshmon/commit/accedc51df94fa8ae6936bb91ad0844fbad83716) - improved monitor stoppage *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`2021762`](https://github.com/rippleFCL/meshmon/commit/2021762411c6fd3c75856ea3580ac17023edd3df) - added reloading for local *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`1e39147`](https://github.com/rippleFCL/meshmon/commit/1e39147d91f46fd6c25db58610a8b334b5630be7) - node_ids and network_ids are parsed as lowercase *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`aa79e01`](https://github.com/rippleFCL/meshmon/commit/aa79e0111d6b3d8e96f59bcdc986c498961a354b) - improved reloading, store now retains data *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`3aa9b83`](https://github.com/rippleFCL/meshmon/commit/3aa9b8319ba645d14d5ab665b3d26a5ae8e0a3a9) - data is deletable now yay! *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :bug: Bug Fixes
- [`1b41552`](https://github.com/rippleFCL/meshmon/commit/1b41552ce5e1dbb817244dac71c27e215e022494) - actually load all the config *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`55d48c9`](https://github.com/rippleFCL/meshmon/commit/55d48c9a483b48346a866dab03f551f4f1b1ba4e) - faulty mtime logic *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`887a630`](https://github.com/rippleFCL/meshmon/commit/887a63080edcacb6ae9a02851e74258fbf7e47e5) - dont write public key if not nessisary to avoide reload loops *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :wrench: Chores
- [`b9ab6cd`](https://github.com/rippleFCL/meshmon/commit/b9ab6cd2cda68cc87178c7e79595cc446813fd6e) - bump version *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v0.2.0] - 2025-09-11
### :bug: Bug Fixes
- [`4bd6110`](https://github.com/rippleFCL/distomon/commit/4bd6110a935d54476c3263401d25daf1cbc7272e) - allow view to return all networks

### :wrench: Chores
- [`985a796`](https://github.com/rippleFCL/distomon/commit/985a796634b8c47d3bcf91194cab27dea0b47dfc) - added confdirs to gitignore
- [`976db1d`](https://github.com/rippleFCL/distomon/commit/976db1dba4c8c9ce7a8b19a45c27f719660e03c7) - bump version

[v0.2.0]: https://github.com/rippleFCL/distomon/compare/v0.1.0...v0.2.0
[v0.4.0]: https://github.com/rippleFCL/meshmon/compare/v0.3.0...v0.4.0
