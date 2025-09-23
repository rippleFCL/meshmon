# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v3.0.2] - 2025-09-23
### :bug: Bug Fixes
- [`f53106b`](https://github.com/rippleFCL/meshmon/commit/f53106be805fb16883e542794493ea515fee49d5) - allowed keys only included nodes with url when it should be all *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :wrench: Chores
- [`7f58f4d`](https://github.com/rippleFCL/meshmon/commit/7f58f4ddc356b293b697247204eeebd7f3607330) - bump version to 3.0.2 *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v3.0.1] - 2025-09-23
### :bug: Bug Fixes
- [`a789476`](https://github.com/rippleFCL/meshmon/commit/a789476f020cd289e7a31550ce46d495d3948640) - update manager incorrectly reloaded *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v3.0.0] - 2025-09-23
### :sparkles: New Features
- [`85322da`](https://github.com/rippleFCL/meshmon/commit/85322da9d080bd13b2c029b19179c49c95a95698) - added distrobuted webhook handling *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v2.1.0] - 2025-09-21
### :sparkles: New Features
- [`8fa8cd2`](https://github.com/rippleFCL/meshmon/commit/8fa8cd2993da6069642e40b1d9c0634ff1712421) - added version constraint to network config *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :bug: Bug Fixes
- [`1e892a1`](https://github.com/rippleFCL/meshmon/commit/1e892a159cd04726a7802b212235ab1887de945c) - reimpliemt gitpython *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v2.0.5] - 2025-09-20
### :wrench: Chores
- [`d130fd2`](https://github.com/rippleFCL/meshmon/commit/d130fd2a3033e1c67f7e7c7b494fe80f8f0c9fd3) - bump version to v2.0.5 *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v2.0.4] - 2025-09-18
### :bug: Bug Fixes
- [`aa0ed88`](https://github.com/rippleFCL/meshmon/commit/aa0ed8859cb5536d2c819b6955b799feeef8b627) - hub nodes in graph actuall reprisent what they mean *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`ba31197`](https://github.com/rippleFCL/meshmon/commit/ba31197f5390b5d76dbfaaf210625f69b62f2377) - correctly build allowed keys *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`7c107ff`](https://github.com/rippleFCL/meshmon/commit/7c107ffabf902c47ebf30a95602d710b9c5a2439) - remove extra keys on allowed keys sertter *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`36464f6`](https://github.com/rippleFCL/meshmon/commit/36464f60f94226d96930173e697a11c16f5c0db9) - analiytics now correctly removes inbound connected if url has recently been set to none *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :wrench: Chores
- [`836c6f2`](https://github.com/rippleFCL/meshmon/commit/836c6f29901a5c10ecf3a2e4d2e2cea519dede62) - bump version *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v2.0.3] - 2025-09-18
### :sparkles: New Features
- [`ce7e9e2`](https://github.com/rippleFCL/meshmon/commit/ce7e9e2736edb53089599fba644c6983c2ea12cf) - add favicon *(commit by [@vellfire](https://github.com/vellfire))*

### :bug: Bug Fixes
- [`afb2def`](https://github.com/rippleFCL/meshmon/commit/afb2def5240bcae24d8dc7f4848c6a402f54ce90) - update title *(commit by [@vellfire](https://github.com/vellfire))*

### :wrench: Chores
- [`420627c`](https://github.com/rippleFCL/meshmon/commit/420627cc8da0169378969dd704c53b7f38f82d83) - bump version *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v2.0.2] - 2025-09-18
### :sparkles: New Features
- [`66677b4`](https://github.com/rippleFCL/meshmon/commit/66677b46ae244a2385d27ddc43fb02350856bc5a) - better monitor stopping mechanics *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`d789c11`](https://github.com/rippleFCL/meshmon/commit/d789c11eaf18a5cde0846eeb13e10c1410feca24) - better thread stopping logic *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`73040db`](https://github.com/rippleFCL/meshmon/commit/73040db8e4bab6f03a81b9a68bb00fa584cc3682) - run monitor and alive ping imidiatly in threads *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v2.0.1] - 2025-09-18
### :bug: Bug Fixes
- [`8477562`](https://github.com/rippleFCL/meshmon/commit/8477562655b265ea9129bd12b8202a2d127c866d) - harden threads so they handle crashes *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v2.0.0] - 2025-09-18
### :boom: BREAKING CHANGES
- due to [`7a21d32`](https://github.com/rippleFCL/meshmon/commit/7a21d32003abf88542925967c1d0ca81f3fc754e) - allowed nullable url *(commit by [@rippleFCL](https://github.com/rippleFCL))*:

  if your network config intends to use this feature you will have to update to v2.0.0


### :sparkles: New Features
- [`3a33c2c`](https://github.com/rippleFCL/meshmon/commit/3a33c2ce0da1c8b3d8cd5b37f585097c7cd33cc7) - added graph in web *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`507d6d6`](https://github.com/rippleFCL/meshmon/commit/507d6d682b34b53565fdc2ea4d67db82895f8339) - improved graph *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`896eb46`](https://github.com/rippleFCL/meshmon/commit/896eb465dcfa7b5d6563abd93be619b197c9e80f) - working on better routing algo *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`756b674`](https://github.com/rippleFCL/meshmon/commit/756b67429b38053766777ac669899141399d4024) - connection are gud now *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`c55a96b`](https://github.com/rippleFCL/meshmon/commit/c55a96b018d70b4dbf60fca012c493d80ca36401) - improved node detail redability *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`3a05435`](https://github.com/rippleFCL/meshmon/commit/3a054359424368db3a7279b2b0d554bc221bc06e) - added a unified view *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`a756bf6`](https://github.com/rippleFCL/meshmon/commit/a756bf6999337506bb2fb58bcb37410cdb555f8a) - added cards insted of a table in unified view *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`7a21d32`](https://github.com/rippleFCL/meshmon/commit/7a21d32003abf88542925967c1d0ca81f3fc754e) - allowed nullable url *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`ad3eb66`](https://github.com/rippleFCL/meshmon/commit/ad3eb668cd0af20422e49fc704df6e542082ce23) - added webhooks *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :bug: Bug Fixes
- [`ddfb526`](https://github.com/rippleFCL/meshmon/commit/ddfb52606669834427bd4714d2eaf34bd1039588) - removed unused values *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :wrench: Chores
- [`7c7c296`](https://github.com/rippleFCL/meshmon/commit/7c7c296e5fda2a268656ddd48be8752c5b1f6a29) - bump version to v2.0.0 *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v1.0.8] - 2025-09-17
### :bug: Bug Fixes
- [`197e7d3`](https://github.com/rippleFCL/meshmon/commit/197e7d332f1233d572c6cdc9aa158a20ec5efcaf) - going cloud native. fixed multi node setups *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :wrench: Chores
- [`c1c4033`](https://github.com/rippleFCL/meshmon/commit/c1c4033e62d2acb0dbea5edc7944382b40833ce6) - bump version to 1.0.8 *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v1.0.7] - 2025-09-17
### :bug: Bug Fixes
- [`078552f`](https://github.com/rippleFCL/meshmon/commit/078552f5a14d0e68796b8c6bbc06505596426c28) - update date formatting to use localeString and fix the "node details" font colour *(commit by [@vellfire](https://github.com/vellfire))*
- [`fcc73b4`](https://github.com/rippleFCL/meshmon/commit/fcc73b4beb095a2c391d4614f51faf9a57c1f9c4) - make dates more consistent *(commit by [@vellfire](https://github.com/vellfire))*
- [`374d29a`](https://github.com/rippleFCL/meshmon/commit/374d29a65ded073bf5a228918fbfc19c661d8ad9) - cutoff too high ping times *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :wrench: Chores
- [`3248fa5`](https://github.com/rippleFCL/meshmon/commit/3248fa5556ffaa3b214ad85a1ce76e6ad470a616) - bump version v1.0.7 *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v1.0.5] - 2025-09-17
### :bug: Bug Fixes
- [`972a18a`](https://github.com/rippleFCL/meshmon/commit/972a18a7409feb08bcf38c13d90a7d10af771ac4) - didnt account for timeout in interval *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`904eabc`](https://github.com/rippleFCL/meshmon/commit/904eabc095767747228a7978e25aeceb926b2b08) - dont dump store on reload *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :wrench: Chores
- [`576da71`](https://github.com/rippleFCL/meshmon/commit/576da71d0bcca5bfc054c93fe5132c6018ccd461) - bump version *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v1.0.4] - 2025-09-17
### :bug: Bug Fixes
- [`6029e4c`](https://github.com/rippleFCL/meshmon/commit/6029e4c4bd435899c65e03f5b05901f32c02510b) - node status was calculated wrong *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`079c766`](https://github.com/rippleFCL/meshmon/commit/079c766b10cb5c599795ddf39a14636914f31047) - increct logging level in analysis *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :wrench: Chores
- [`5dd9b15`](https://github.com/rippleFCL/meshmon/commit/5dd9b158e67afb60f37bdb966a8aed0624139c21) - bump version *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v1.0.1] - 2025-09-17
### :bug: Bug Fixes
- [`8e264ca`](https://github.com/rippleFCL/meshmon/commit/8e264cae101845317461958b4ec7bc025e69a76e) - store callback to prefill on creation *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`d29b200`](https://github.com/rippleFCL/meshmon/commit/d29b200f411666016bd994520eebe54b7a1ce835) - config reload loop *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`56ebe04`](https://github.com/rippleFCL/meshmon/commit/56ebe04f12b0b3f9a6a98d2d871178d3aa99f411) - off by one error *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :wrench: Chores
- [`402f078`](https://github.com/rippleFCL/meshmon/commit/402f078a283e8948d97815c98a66c95b1683f2ad) - bump version *(commit by [@rippleFCL](https://github.com/rippleFCL))*


## [v1.0.0] - 2025-09-17
### :sparkles: New Features
- [`fd8ecbe`](https://github.com/rippleFCL/meshmon/commit/fd8ecbefb1991e7a8d94e489ded5623190dd00c7) - added network analysis *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`e93c2d4`](https://github.com/rippleFCL/meshmon/commit/e93c2d4272058f89bd27d432ee62cbd9f5a7da33) - frontend v0.0.1 *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`af1423e`](https://github.com/rippleFCL/meshmon/commit/af1423eb8061f45c325ae6593b470f308b5bc7c7) - impvoed web stuff *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`4068f63`](https://github.com/rippleFCL/meshmon/commit/4068f63b363680e1a41e8626d0e6254411100423) - proper reloading *(commit by [@rippleFCL](https://github.com/rippleFCL))*
- [`4544bda`](https://github.com/rippleFCL/meshmon/commit/4544bda187a2c7a7f36e43f9493b7fd171ee96fb) - packaged into one container *(commit by [@rippleFCL](https://github.com/rippleFCL))*

### :wrench: Chores
- [`a337eaa`](https://github.com/rippleFCL/meshmon/commit/a337eaa8d1251f1102419603e57538a358e8a200) - bump version to 1.0.0 *(commit by [@rippleFCL](https://github.com/rippleFCL))*


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
[v1.0.0]: https://github.com/rippleFCL/meshmon/compare/v0.4.0...v1.0.0
[v1.0.1]: https://github.com/rippleFCL/meshmon/compare/v1.0.0...v1.0.1
[v1.0.4]: https://github.com/rippleFCL/meshmon/compare/v1.0.3...v1.0.4
[v1.0.5]: https://github.com/rippleFCL/meshmon/compare/v1.0.4...v1.0.5
[v1.0.7]: https://github.com/rippleFCL/meshmon/compare/v1.0.6...v1.0.7
[v1.0.8]: https://github.com/rippleFCL/meshmon/compare/v1.0.7...v1.0.8
[v2.0.0]: https://github.com/rippleFCL/meshmon/compare/v1.0.8...v2.0.0
[v2.0.1]: https://github.com/rippleFCL/meshmon/compare/v2.0.0...v2.0.1
[v2.0.2]: https://github.com/rippleFCL/meshmon/compare/v2.0.1...v2.0.2
[v2.0.3]: https://github.com/rippleFCL/meshmon/compare/v2.0.2...v2.0.3
[v2.0.4]: https://github.com/rippleFCL/meshmon/compare/v2.0.3...v2.0.4
[v2.0.5]: https://github.com/rippleFCL/meshmon/compare/v2.0.4...v2.0.5
[v2.1.0]: https://github.com/rippleFCL/meshmon/compare/v2.0.5...v2.1.0
[v3.0.0]: https://github.com/rippleFCL/meshmon/compare/v2.1.0...v3.0.0
[v3.0.1]: https://github.com/rippleFCL/meshmon/compare/v3.0.0...v3.0.1
[v3.0.2]: https://github.com/rippleFCL/meshmon/compare/v3.0.1...v3.0.2
