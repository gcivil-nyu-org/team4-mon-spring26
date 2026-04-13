# High-Level Analysis

## High-Level Context Diagram

![High-Level Context Diagram](https://raw.githubusercontent.com/gcivil-nyu-org/team4-mon-spring26/develop/assets/wiki.png)

**TenantGuard NYC** is an ML-powered web application that helps prospective and current tenants in New York City evaluate building safety by aggregating and scoring public housing data. The platform ingests violations, complaints, and registration data from NYC Open Data (HPD / 311) on a weekly batch basis, computes area-based risk and safety scores, and surfaces this information through an interactive city heatmap, building profiles, and community discussions.

---

## User Personas

### Prospective Tenant / Public User

Prospective tenants are individuals who are searching for housing in New York City and want to make informed decisions about the safety and livability of potential buildings and neighborhoods. These users do not need an account to access core features of the platform.

A prospective tenant can:

- **Search & Browse the City Heatmap** -- Explore an interactive map of NYC that visually highlights areas by risk level, allowing users to quickly identify safer neighborhoods.
- **View Building Profile & Risk Score** -- Access detailed profiles for individual buildings, including an ML-generated risk score derived from historical HPD violations, 311 complaints, and registration data.
- **Read Neighborhood / Building Discussions** -- Browse community-driven discussion threads tied to specific neighborhoods or buildings to learn from the experiences of current and past tenants.
- **Subscribe to Risk-Change Alerts (Area-based)** -- Sign up for notifications when the risk score of a specific area or building changes significantly, enabling proactive awareness of deteriorating or improving conditions.
- **View Landlord Portfolio** -- Examine a landlord's full portfolio of properties along with aggregated risk scores and violation histories, helping tenants assess whether a landlord has a pattern of neglect.

### Verified Tenant

Verified tenants are current or former NYC tenants who have authenticated their identity on the platform. They have all the capabilities of a prospective tenant, plus additional community participation features that help build a trusted, tenant-driven knowledge base.

A verified tenant can do everything a prospective tenant can, plus:

- **Post / Report Posts (or Users) in Neighbourhood Community** -- Create new discussion posts in neighborhood-level community forums to share experiences, ask questions, or warn other tenants about building issues. Verified tenants can also report posts or users that violate community guidelines.
- **Upvote / Downvote Posts** -- Vote on community posts to surface the most helpful and relevant content, ensuring high-quality information rises to the top.

### Administrator

Administrators are platform moderators responsible for maintaining the integrity and safety of the community. They ensure that community discussions remain constructive and that user permissions are properly managed.

An administrator can:

- **Moderate Flagged Posts (or Users)** -- Review posts and user accounts that have been flagged/reported by verified tenants. Administrators can remove inappropriate content, issue warnings, or take disciplinary action against users who repeatedly violate community guidelines.
- **Manage Users & Permissions** -- Oversee user accounts, verify tenant status, adjust user roles and permissions, and handle account-related issues such as bans or suspensions.

---

## Epics

### NYC Areawise Interactive Map
- As a user, I want to browse an interactive heatmap of NYC color-coded by risk level so I can identify safer neighborhoods.
- As a user, I want to search for a specific address or neighborhood on the map so I can evaluate a location I'm considering.

### User Roles and Verification
- As a user, I want to create an account and log in so I can access personalized features.
- As a tenant, I want to submit verification documentation so I can be granted verified status and participate in the community.

### Area Based Communities
- As a user, I want to read neighborhood and building discussion threads so I can learn from other tenants' experiences.
- As a verified tenant, I want to create posts and reply to threads in my neighborhood forum so I can share my experiences.
- As a verified tenant, I want to upvote or downvote posts so the most helpful content is surfaced.

### Report Users and Posts
- As a verified tenant, I want to report posts or users that violate community guidelines so the community stays trustworthy.

### DM For Users and Reporting
- As a verified tenant, I want to directly message other users so I can have private conversations about building or neighborhood concerns.
- As a user, I want to report inappropriate direct messages so that abuse can be addressed.

### Admin Dashboard
- As an admin, I want to review flagged posts and users so I can take appropriate moderation action.
- As an admin, I want to manage user roles, permissions, and bans so the platform remains safe.
- As an admin, I want to verify tenant documentation submissions so only legitimate tenants gain verified status.

### Public Portfolio for Landlords
- As a user, I want to view a landlord's full portfolio of properties with aggregated risk scores so I can assess their track record.
- As a user, I want to see violation histories across a landlord's buildings so I can identify patterns of neglect.

### Weekly Cron Jobs for Data Ingestion and Score Updates
- As a platform, I want to ingest HPD violation and 311 complaint data weekly so building risk scores stay current.
- As a platform, I want to recalculate area-based safety scores on each ingestion so trends remain visible.

### Risk Change (Calculation and Alerts)
- As a user, I want to see how a building's or area's risk score has changed over time so I can spot improving or worsening trends.
- As a user, I want to be notified when a subscribed area's risk score changes significantly.

### User Subscription and Delivery for Area Based Risk Alert
- As a user, I want to subscribe to risk-change alerts for specific areas or buildings so I'm informed when conditions change.
- As a user, I want to manage my alert subscriptions and choose my delivery preference (email, in-app) so I only get notifications I care about.
