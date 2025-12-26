import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
    console.log("Seeding database...");

    // Create default user
    const user = await prisma.user.upsert({
        where: { id: "default-user" },
        update: {},
        create: {
            id: "default-user",
            email: "demo@tryfitted.com",
        },
    });

    console.log("Created default user:", user);
}

main()
    .then(async () => {
        await prisma.$disconnect();
    })
    .catch(async (e) => {
        console.error(e);
        await prisma.$disconnect();
        process.exit(1);
    });
