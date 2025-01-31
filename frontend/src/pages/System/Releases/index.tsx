import { useSystemReleases } from "@/apis/hooks";
import { QueryOverlay } from "@/components/async";
import { BuildKey } from "@/utilities";
import {
  Badge,
  Card,
  Container,
  Divider,
  Group,
  List,
  Stack,
  Text,
} from "@mantine/core";
import { useDocumentTitle } from "@mantine/hooks";
import { FunctionComponent, useMemo } from "react";

const SystemReleasesView: FunctionComponent = () => {
  const releases = useSystemReleases();
  const { data } = releases;

  useDocumentTitle("Releases - Bazarr (System)");

  return (
    <Container size={600} py={12}>
      <QueryOverlay result={releases}>
        <Stack spacing="lg">
          {data?.map((v, idx) => (
            <ReleaseCard key={BuildKey(idx, v.date)} {...v}></ReleaseCard>
          ))}
        </Stack>
      </QueryOverlay>
    </Container>
  );
};

const ReleaseCard: FunctionComponent<ReleaseInfo> = ({
  name,
  body,
  date,
  prerelease,
  current,
}) => {
  const infos = useMemo(
    () => body.map((v) => v.replace(/(\s\[.*?\])\(.*?\)/, "")),
    [body]
  );
  return (
    <Card shadow="md" p="lg">
      <Group>
        <Text weight="bold">{name}</Text>
        <Badge color="blue">{date}</Badge>
        <Badge color={prerelease ? "yellow" : "green"}>
          {prerelease ? "Development" : "Master"}
        </Badge>
        <Badge hidden={!current} color="indigo">
          Installed
        </Badge>
      </Group>
      <Divider my="sm"></Divider>
      <Text>From newest to oldest:</Text>
      <List>
        {infos.map((v, idx) => (
          <List.Item key={idx}>{v}</List.Item>
        ))}
      </List>
    </Card>
  );
};

export default SystemReleasesView;
